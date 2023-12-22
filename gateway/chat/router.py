import json
import re
import time
from collections import defaultdict
from typing import List
import base64

from PIL import Image
from io import BytesIO
from os import getcwd
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from fastapi_jwt_auth import AuthJWT
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from models import Customer, ChatRoom, ChatRoom, ChatRoomMessage
from chat.schemas import MessagesModel, Pagination
from config.database import async_session_maker, get_async_session

router = APIRouter(
    prefix="/v1/chat",
    tags=["Chat"]
)


async def get_user_by_id(id: int, session: AsyncSession):
    result = await session.execute(select(Customer).where((Customer.id == id)))
    user = result.first()
    if user:
        return user[0]
    return None


class ConnectionManager:
    def __init__(self):
        self.connections: dict = defaultdict(dict)
        self.generator = self.get_notification_generator()

    async def connect(self, websocket: WebSocket, room_id: int):
        await websocket.accept()
        if self.connections[room_id] == {} or len(self.connections[room_id]) == 0:
            self.connections[room_id] = []
        self.connections[room_id].append(websocket)

    def disconnect(self, websocket: WebSocket, room_id: int):
        self.connections[room_id].remove(websocket)

    async def get_notification_generator(self):
        while True:
            message = yield
            msg = message["message"]
            room_name = message["room_name"]
            await self._notify(msg, room_name)

    def get_members(self, room_id: int):
        try:
            return self.connections[room_id]
        except Exception:
            return None

    async def broadcast(self, message: dict, room_id: int, sender_id: int, session: AsyncSession):
        message_text = message['message']
        message_file = message['file']
        image_data = re.sub('^data:image/.+;base64,', '', message['file'])
        im = Image.open(BytesIO(base64.b64decode(image_data)))
        im.save(f"{getcwd()}/chat/media/order/{room_id}/{int(time.time()*1000)}.png")
        msg = await self.add_messages_to_database(message_text, room_id, sender_id)
        member = await get_user_by_id(sender_id, session)
        if not member:
            return
        data = {'message': message_text, 'file': '',
                'sender': {'id': sender_id, 'username': member.display_name}, 'sent': msg.created_at}
        for connection in self.connections[room_id]:
            try:
                await connection.send_text(f'{data}')
            except:
                self.connections[room_id].remove(connection)

    @staticmethod
    async def add_messages_to_database(message: str, room_id: int, sender_id: int, file_path: str | None = None):
        async with async_session_maker() as session:
            msg = ChatRoomMessage(
                message=message,
                room_id=room_id,
                creator_id=sender_id,
                file=file_path
            )
            session.add(msg)
            await session.commit()
        return msg


manager = ConnectionManager()


@router.get("/last_messages/{room_id}")
async def get_last_messages(room_id: int, limit: int, page: int, Authorize: AuthJWT = Depends(),
                            session: AsyncSession = Depends(get_async_session), ) -> List[MessagesModel]:
    Authorize.jwt_required()
    current_user = Authorize.get_jwt_subject()
    if not (await session.execute(
            select(ChatRoom).where(
                (ChatRoom.id == room_id) & (
                        (ChatRoom.offer_member_id == current_user) | (
                        ChatRoom.order_member_id == current_user))))).first():
        raise HTTPException(
            status_code=403,
            detail='you_have_no_access_to_this_chat'
        )
    query = select(ChatRoomMessage).where(ChatRoomMessage.room_id == room_id).order_by(
        ChatRoomMessage.created_at.desc())
    messages = await session.execute(query)
    return JSONResponse(
        status_code=200,
        content={"messages": [
            {
                'id': i.id,
                'member': i.creator_id,
                'message': i.message,
                'sent': i.created_at.strftime("%d/%m/%Y, %H:%M:%S")
            }
            for i in messages.scalars().all()[limit * (page - 1): limit * page]]}
    )


@router.websocket('/ws/{room_id}')
async def websocket(websocket: WebSocket, room_id: int, token: str = Query(...), Authorize: AuthJWT = Depends(),
                    session: AsyncSession = Depends(get_async_session)):
    Authorize.jwt_required("websocket", token=token)
    decoded_token = Authorize.get_raw_jwt(token)
    current_user = decoded_token['sub']
    if not (await session.execute(
            select(ChatRoom).where(
                (ChatRoom.id == room_id) & ((ChatRoom.offer_member_id == current_user) |
                                            (ChatRoom.order_member_id == current_user))))).first():
        raise HTTPException(
            status_code=403,
            detail='you_have_no_access_to_this_chat'
        )
    await manager.connect(websocket, room_id)
    try:
        while True:
            data = await websocket.receive_json()
            await manager.broadcast(data, room_id, current_user, session)
    except WebSocketDisconnect:
        manager.disconnect(websocket, room_id)
