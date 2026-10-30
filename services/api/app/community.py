"""Channels and simple keyword-reply bots for Vainah Messenger MVP.

Channels are public to signed-in users. The owner controls posts.
Bots are deterministic phrase-reply helpers; they do not run arbitrary code.
"""
from __future__ import annotations
import time
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint, func, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from .database import Base, get_db
from .models import User, uid, VerifiedAccount
from .handles import find_by_username, username_for, blocked
from .security import csrf_protect, current_user, enforce_origin

router = APIRouter(prefix="/api/community", tags=["Messenger channels and bots"])


class Channel(Base):
    __tablename__ = "messenger_channels"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(String(300), default="")
    created_at: Mapped[int] = mapped_column(Integer, default=lambda: int(time.time()))


class ChannelMember(Base):
    __tablename__ = "messenger_channel_members"
    __table_args__ = (UniqueConstraint("channel_id", "user_id", name="uq_channel_subscriber"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    channel_id: Mapped[str] = mapped_column(ForeignKey("messenger_channels.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)


class ChannelInvitation(Base):
    __tablename__ = "messenger_channel_invitations"
    __table_args__ = (UniqueConstraint("channel_id", "user_id", name="uq_channel_invitation_target"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    channel_id: Mapped[str] = mapped_column(ForeignKey("messenger_channels.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    invited_by: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    created_at: Mapped[int] = mapped_column(Integer, default=lambda: int(time.time()))

class ChannelInviteRequest(BaseModel):
    username: str = Field(min_length=3, max_length=33)

class ChannelPost(Base):
    __tablename__ = "messenger_channel_posts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    channel_id: Mapped[str] = mapped_column(ForeignKey("messenger_channels.id", ondelete="CASCADE"), index=True)
    body: Mapped[str] = mapped_column(Text())
    created_at: Mapped[int] = mapped_column(Integer, default=lambda: int(time.time()))


class SimpleBot(Base):
    __tablename__ = "messenger_bots"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(String(300), default="")


class BotRule(Base):
    __tablename__ = "messenger_bot_rules"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    bot_id: Mapped[str] = mapped_column(ForeignKey("messenger_bots.id", ondelete="CASCADE"), index=True)
    trigger: Mapped[str] = mapped_column(String(80))
    reply: Mapped[str] = mapped_column(String(1000))


class CreateCommunity(BaseModel):
    name: str = Field(min_length=2,max_length=80)
    description: str = Field(default="",max_length=300)


class NewPost(BaseModel):
    body: str = Field(min_length=1,max_length=4000)


class NewRule(BaseModel):
    trigger: str = Field(min_length=2,max_length=80)
    reply: str = Field(min_length=1,max_length=1000)


class BotQuestion(BaseModel):
    message: str = Field(min_length=1,max_length=500)


def gate(request: Request) -> None:
    enforce_origin(request)


def require_channel(db: Session, channel_id: str) -> Channel:
    channel = db.get(Channel,channel_id)
    if not channel:
        raise HTTPException(404,"Канал не найден")
    return channel


def require_bot(db: Session, bot_id: str) -> SimpleBot:
    bot = db.get(SimpleBot,bot_id)
    if not bot:
        raise HTTPException(404,"Бот не найден")
    return bot


@router.get("/channels")
def channels(db: Session=Depends(get_db), user: User=Depends(current_user)):
    items = db.scalars(select(Channel).order_by(Channel.created_at.desc()).limit(100)).all()
    subs = set(db.scalars(select(ChannelMember.channel_id).where(ChannelMember.user_id==user.id)).all())
    verified = set(db.scalars(select(VerifiedAccount.user_id).where(
        VerifiedAccount.user_id.in_([c.owner_id for c in items]))).all()) if items else set()
    return {"items":[{"id":c.id,"name":c.name,"description":c.description,"owner":c.owner_id==user.id,
                       "subscribed":c.id in subs or c.owner_id==user.id,
                       "verified":c.owner_id in verified} for c in items]}


@router.post("/channels",status_code=201,dependencies=[Depends(csrf_protect)])
def create_channel(data:CreateCommunity,request:Request,db:Session=Depends(get_db),user:User=Depends(current_user)):
    gate(request)
    if db.scalar(select(func.count()).select_from(Channel).where(Channel.owner_id==user.id)) >= 10:
        raise HTTPException(429,"Не более 10 каналов на аккаунт")
    channel=Channel(owner_id=user.id,name=data.name.strip(),description=data.description.strip())
    if len(channel.name)<2:raise HTTPException(422,"Укажите название канала")
    db.add(channel);db.commit()
    return {"id":channel.id}


@router.post("/channels/{channel_id}/subscribe",dependencies=[Depends(csrf_protect)])
def subscribe(channel_id:str,request:Request,db:Session=Depends(get_db),user:User=Depends(current_user)):
    gate(request)
    channel=require_channel(db,channel_id)
    if channel.owner_id!=user.id and not db.scalar(select(ChannelMember).where(
        ChannelMember.channel_id==channel_id,ChannelMember.user_id==user.id)):
        db.add(ChannelMember(channel_id=channel_id,user_id=user.id));db.commit()
    return {"ok":True}


@router.delete("/channels/{channel_id}/subscribe",dependencies=[Depends(csrf_protect)])
def unsubscribe(channel_id:str,request:Request,db:Session=Depends(get_db),user:User=Depends(current_user)):
    gate(request)
    channel=require_channel(db,channel_id)
    if channel.owner_id==user.id:raise HTTPException(403,"Владелец не может отписаться")
    membership=db.scalar(select(ChannelMember).where(
        ChannelMember.channel_id==channel_id,ChannelMember.user_id==user.id))
    if membership:db.delete(membership);db.commit()
    return {"ok":True}


@router.get("/channels/invitations")
def list_channel_invitations(db:Session=Depends(get_db),user:User=Depends(current_user)):
    rows=db.scalars(select(ChannelInvitation).where(ChannelInvitation.user_id==user.id)
                    .order_by(ChannelInvitation.created_at.desc()).limit(30)).all()
    items=[]
    for invite in rows:
        channel=db.get(Channel,invite.channel_id)
        if channel:
            items.append({"id":invite.id,"channel_id":channel.id,"channel_name":channel.name,
                          "invited_by":username_for(db,invite.invited_by)})
    return {"items":items}


@router.post("/channels/invitations/{invitation_id}/accept",dependencies=[Depends(csrf_protect)])
def accept_channel_invitation(invitation_id:str,request:Request,db:Session=Depends(get_db),
                              user:User=Depends(current_user)):
    gate(request)
    invitation=db.get(ChannelInvitation,invitation_id)
    if not invitation or invitation.user_id!=user.id:
        raise HTTPException(404,"Приглашение не найдено")
    channel=require_channel(db,invitation.channel_id)
    if not db.scalar(select(ChannelMember).where(ChannelMember.channel_id==channel.id,
                                                ChannelMember.user_id==user.id)):
        db.add(ChannelMember(channel_id=channel.id,user_id=user.id))
    db.delete(invitation)
    db.commit()
    return {"ok":True,"channel_id":channel.id}


@router.delete("/channels/invitations/{invitation_id}",dependencies=[Depends(csrf_protect)])
def decline_channel_invitation(invitation_id:str,request:Request,db:Session=Depends(get_db),
                               user:User=Depends(current_user)):
    gate(request)
    invitation=db.get(ChannelInvitation,invitation_id)
    if not invitation or invitation.user_id!=user.id:
        raise HTTPException(404,"Приглашение не найдено")
    db.delete(invitation)
    db.commit()
    return {"ok":True}


@router.post("/channels/{channel_id}/invite",dependencies=[Depends(csrf_protect)])
def invite_to_channel(channel_id:str,data:ChannelInviteRequest,request:Request,
                      db:Session=Depends(get_db),user:User=Depends(current_user)):
    gate(request)
    channel=require_channel(db,channel_id)
    if channel.owner_id!=user.id:
        raise HTTPException(403,"Приглашать в канал может только владелец")
    target=find_by_username(db,data.username)
    if not target or target.id==user.id:
        raise HTTPException(404,"Пользователь не найден")
    if blocked(db,user.id,target.id):
        raise HTTPException(403,"Пользователь недоступен")
    if db.scalar(select(ChannelMember).where(ChannelMember.channel_id==channel_id,
                                             ChannelMember.user_id==target.id)):
        raise HTTPException(409,"Пользователь уже подписан")
    existing=db.scalar(select(ChannelInvitation).where(ChannelInvitation.channel_id==channel_id,
                                                        ChannelInvitation.user_id==target.id))
    if existing:
        raise HTTPException(409,"Приглашение уже отправлено")
    pending=db.scalar(select(func.count(ChannelInvitation.id)).where(
        ChannelInvitation.invited_by==user.id)) or 0
    if pending>=40:
        raise HTTPException(429,"Лимит ожидающих приглашений достигнут")
    db.add(ChannelInvitation(channel_id=channel_id,user_id=target.id,invited_by=user.id))
    try: db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(409,"Приглашение уже создано")
    return {"ok":True}


@router.get("/channels/{channel_id}/posts")
def posts(channel_id:str,db:Session=Depends(get_db),user:User=Depends(current_user)):
    require_channel(db,channel_id)
    items=db.scalars(select(ChannelPost).where(ChannelPost.channel_id==channel_id)
                     .order_by(ChannelPost.created_at.desc()).limit(100)).all()
    return {"items":[{"id":p.id,"body":p.body,"created_at":p.created_at} for p in items]}


@router.post("/channels/{channel_id}/posts",status_code=201,dependencies=[Depends(csrf_protect)])
def post(channel_id:str,data:NewPost,request:Request,db:Session=Depends(get_db),user:User=Depends(current_user)):
    gate(request);channel=require_channel(db,channel_id)
    if channel.owner_id!=user.id:raise HTTPException(403,"Только владелец может публиковать")
    if not data.body.strip():raise HTTPException(422,"Сообщение пустое")
    p=ChannelPost(channel_id=channel_id,body=data.body.strip());db.add(p);db.commit()
    return {"id":p.id}


@router.get("/bots")
def bots(db:Session=Depends(get_db),user:User=Depends(current_user)):
    items=db.scalars(select(SimpleBot).order_by(SimpleBot.name).limit(100)).all()
    return {"items":[{"id":b.id,"name":b.name,"description":b.description,"owner":b.owner_id==user.id} for b in items]}


@router.post("/bots",status_code=201,dependencies=[Depends(csrf_protect)])
def create_bot(data:CreateCommunity,request:Request,db:Session=Depends(get_db),user:User=Depends(current_user)):
    gate(request)
    if db.scalar(select(func.count()).select_from(SimpleBot).where(SimpleBot.owner_id==user.id))>=5:
        raise HTTPException(429,"Не более 5 ботов на аккаунт")
    bot=SimpleBot(owner_id=user.id,name=data.name.strip(),description=data.description.strip())
    if len(bot.name)<2:raise HTTPException(422,"Укажите название бота")
    db.add(bot);db.commit()
    return {"id":bot.id}


@router.post("/bots/{bot_id}/rules",status_code=201,dependencies=[Depends(csrf_protect)])
def add_rule(bot_id:str,data:NewRule,request:Request,db:Session=Depends(get_db),user:User=Depends(current_user)):
    gate(request);bot=require_bot(db,bot_id)
    if bot.owner_id!=user.id:raise HTTPException(403,"Только владелец изменяет бота")
    if db.scalar(select(func.count()).select_from(BotRule).where(BotRule.bot_id==bot_id))>=20:
        raise HTTPException(429,"Максимум 20 ответов")
    trigger=data.trigger.strip().casefold()
    if len(trigger)<2:raise HTTPException(422,"Укажите ключевое слово")
    rule=BotRule(bot_id=bot_id,trigger=trigger,reply=data.reply.strip())
    db.add(rule);db.commit()
    return {"id":rule.id}


@router.post("/bots/{bot_id}/reply")
def reply(bot_id:str,data:BotQuestion,db:Session=Depends(get_db),user:User=Depends(current_user)):
    require_bot(db,bot_id)
    text=data.message.casefold()
    rules=db.scalars(select(BotRule).where(BotRule.bot_id==bot_id).limit(20)).all()
    response=next((r.reply for r in rules if r.trigger in text),None)
    return {"reply":response or "Пока нет ответа на этот запрос."}
