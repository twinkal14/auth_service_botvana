from jose import jwt, JWTError
from datetime import datetime, timedelta
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer

# Secret key for signing tokens (Keep this in .env in production)
SECRET_KEY = "boffins-secret-key"
ALGORITHM = "HS256"
EXPIRE_MINUTES = 30

# Tells FastAPI where to look for token (used in Swagger docs)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")  # matches your /login route

#  Create a JWT token for a given username
#def create_jwt_token(username: str) -> str:
    # Set token expiration time
    #expire = datetime.utcnow() + timedelta(minutes=EXPIRE_MINUTES)
    # Add username and expiry to the token payload
    #payload = {"sub": username, "exp": expire}
    # Encode the payload into a JWT string
    #return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def create_jwt_token(username: str, role: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=EXPIRE_MINUTES)
    payload = {"sub": username, "role": role, "exp": expire}  #  add role
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


#  Decode and verify a token, return username if valid
#def verify_jwt_token(token: str) -> str | None:
    #try:
        # Decode token using secret key and algorithm
        #payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        #return payload.get("sub")  # Get the username
    #except JWTError:
        #return None  # Token is invalid or expired

def verify_jwt_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return {"username": payload.get("sub"), "role": payload.get("role")}
    except JWTError:
        return None


#  Reusable FastAPI dependency to extract user from token
#def get_current_user(token: str = Depends(oauth2_scheme)) -> str:
    # Decode and validate the token
    #username = verify_jwt_token(token)
    #if not username:
        #raise HTTPException(status_code=401, detail="Invalid or expired token")
    #return username

def get_current_user(token: str = Depends(oauth2_scheme)):
    data = verify_jwt_token(token)
    if not data:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return data  # returns dict: {'username': 'shekhar', 'role': 'admin'}

