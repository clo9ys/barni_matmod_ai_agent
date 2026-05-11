from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlmodel import Session, select
from src.core.database import User, get_session
from src.core.security import hash_password, verify_password, create_access_token, ALGORITHM, SECRET_KEY
from jose import jwt

router = APIRouter(prefix="/auth", tags=["auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_session)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="невалидный токен")
    except Exception:
        raise HTTPException(status_code=401, detail="ошибка авторизации")

    user = db.exec(select(User).where(User.username == username)).first()
    if user is None:
        raise HTTPException(status_code=401, detail="пользователь не найден")
    return user


@router.post("/register")
async def register(username: str, password: str, db: Session = Depends(get_session)):
    existing = db.exec(select(User).where(User.username == username)).first()
    if existing:
        raise HTTPException(status_code=400, detail="логин занят")

    user = User(username=username, hashed_password=hash_password(password))
    db.add(user)
    db.commit()
    return {"status": "ok"}


@router.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_session)):
    user = db.exec(select(User).where(User.username == form_data.username)).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="неверный логин или пароль")

    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}