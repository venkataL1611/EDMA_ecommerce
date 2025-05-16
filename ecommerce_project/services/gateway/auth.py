from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from shared.auth import decode_token, TokenData

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    token_data = decode_token(token)
    if token_data is None:
        raise credentials_exception
    return token_data

async def get_current_active_user(current_user: TokenData = Depends(get_current_user)):
    # Here you would typically check if user is active in your database
    return current_user