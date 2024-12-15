from fastapi import FastAPI, HTTPException, BackgroundTasks, status, Request
from pydantic import BaseModel
from fastapi_pagination import Page, add_pagination, paginate
from fastapi_pagination.utils import disable_installed_extensions_check
disable_installed_extensions_check()
from typing import List, Optional
import mysql.connector
from discord import SyncWebhook
import time
import uuid
from fastapi.middleware.cors import CORSMiddleware
import requests
from urllib.parse import quote, urlencode
import os

db_config = {
    'user': 'root',
    'password': 'dbuserdbuser',
    'host': os.environ.get('DB_HOST', '34.46.34.153'),
    'database': 'w4153'
}

app = FastAPI(title='users')
add_pagination(app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class BasicResponse(BaseModel):
    message: str
    links: dict

class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    links: dict

# middleware to log all requests
@app.middleware("http")
async def sql_logging(request: Request, call_next):
    start_time = time.perf_counter()

    headers = dict(request.scope['headers'])

    if b'x-correlation-id' not in headers:
        correlation_id = str(uuid.uuid4())
        headers[b'x-correlation-id'] = correlation_id.encode('latin-1')
        request.scope['headers'] = [(k, v) for k, v in headers.items()]
    else:
        correlation_id = request.headers['x-correlation-id']

    response = await call_next(request)

    process_time = time.perf_counter() - start_time
    
    with mysql.connector.connect(**db_config) as conn:
        with conn.cursor(dictionary=True) as cursor:
            query = "INSERT INTO logs (microservice, request, response, elapsed, correlation_id) VALUES (%s, %s, %s, %s, %s)"
            values = ('users', str(request.url.path), str(response.status_code), int(process_time), correlation_id)
            cursor.execute(query, values)
            conn.commit()
        
    return response

# basic hello world for the microservice
@app.get("/")
def get_microservice() -> BasicResponse:
    """
    Simple endpoint to test and return which microservice is being connected to.
    """
    return BasicResponse(message="hello world from users microservice", links={})

# get user by id
@app.get("/users/{user_id}")
def get_user(user_id: int) -> Optional[UserResponse]:
    """
    Get a User by its id from the database.
    """
    with mysql.connector.connect(**db_config) as conn:
        with conn.cursor(dictionary=True) as cursor:
            query = "SELECT id, name, email FROM users WHERE id = %s"
            values = (user_id,)
            cursor.execute(query, values)
            
            row = cursor.fetchone()
            if row:
                user = UserResponse(id=row['id'], name=row['name'], email=row['email'], links={'get': f'/users/{row["id"]}'})
                return user
            else:
                return HTTPException(status_code=404, detail=f'user_id {user_id} not found')

# get all users
@app.get("/users")
def get_users() -> Page[UserResponse]:
    """
    Get all Users in the database.
    """
    with mysql.connector.connect(**db_config) as conn:
        with conn.cursor(dictionary=True) as cursor:
            query = "SELECT id, name, email FROM users"
            cursor.execute(query)
            
            rows = cursor.fetchall()
            if rows:
                users = [UserResponse(id=row['id'], name=row['name'], email=row['email'], links={'get': f'/users/{row["id"]}'}) for row in rows]
                return paginate(users)
            else:
                return HTTPException(status_code=400, detail=f'bad request to users table')

# post new user
@app.post("/users", status_code=201)
def post_user(name: str, email: str) -> UserResponse:
    """
    Post a new User to the database.
    """
    with mysql.connector.connect(**db_config) as conn:
        with conn.cursor(dictionary=True) as cursor:
            query = "INSERT INTO users (name, email) VALUES (%s, %s)"
            values = (name, email)
            cursor.execute(query, values)

            conn.commit()
            
            new_id = cursor.lastrowid

            webhook = SyncWebhook.from_url("https://discord.com/api/webhooks/1315736429850263593/W5U3TYFLLZMTJS3ijBUqMm_0X3XpGbCsgSev2lcLIIEEuDCwLYfl2j5nCjgSX5sfJEQp")
            webhook.send(f"created user with id {new_id}.")

            user = UserResponse(id=new_id, name=name, email=email, links={'get': f'/users/{new_id}'})
            return user

# put user update
@app.put("/users/{user_id}")
def put_user(user_id: int, name: str, email: str) -> Optional[UserResponse]:
    """
    Update a User's name and email specified by its id.
    """
    with mysql.connector.connect(**db_config) as conn:
        with conn.cursor(dictionary=True) as cursor:
            query = "UPDATE users SET name = %s, email = %s WHERE id = %s"
            values = (name, email, user_id)
            cursor.execute(query, values)
            
            updated = cursor.rowcount > 0
            conn.commit()
            
            if updated > 0:
                user = UserResponse(id=user_id, name=name, email=email, links={'get': f'/users/{user_id}'})
                return user
            else:
                return HTTPException(status_code=404, detail=f'user_id {user_id} not found')

task_status = dict()

# async post user
@app.post("/users/async", status_code=202)
async def async_post_user(name: str, email: str, background_tasks: BackgroundTasks) -> BasicResponse:
    """
    Create a new user with the given name and email. Performs update asynchronously (and usually takes around 10s to take effect).
    """
    def wait_post_user(user_id: int, name: str, email: str, task_id: str):
        time.sleep(10)
        post_user(name, email)
        task_status[task_id] = 'done'

    task_id = str(uuid.uuid4())
    task_status[task_id] = 'working'
    background_tasks.add_task(wait_post_user, name, email, task_id)

    return {'message': f'successfully accepted post for user', 'links': {'status': f'/users/async/{task_id}'}}

# async put user update
@app.put("/users/async/{user_id}", status_code=202)
async def async_put_user(user_id: int, name: str, email: str, background_tasks: BackgroundTasks) -> BasicResponse:
    """
    Update a User's name and email specified by its id. Performs update asynchronously (and usually takes around 10s to take effect).
    """
    def wait_put_user_name(user_id: int, name: str, email: str, task_id: str):
        time.sleep(10)
        put_user(user_id, name, email)
        task_status[task_id] = 'done'

    task_id = str(uuid.uuid4())
    task_status[task_id] = 'working'
    background_tasks.add_task(wait_put_user_name, user_id, name, email, task_id)

    return {'message': f'successfully accepted put for user id {user_id}', 'links': {'get': f'/users/{user_id}', 'status': f'/users/async/{task_id}'}}

# async get task update
@app.get("/users/async_check/{task_id}")
def get_async_status(task_id: str) -> BasicResponse:
    """
    Checks the async task status based on the task id.
    """
    if task_id not in task_status:
        return HTTPException(status_code=404, detail=f'task id {task_id} not found')
    elif task_status[task_id] != 'done':
        return BasicResponse(message=f'task {task_id} still in progress', links={'status': f"/users/async_check/{task_id}"})
    else:
        return BasicResponse(message=f'task {task_id} has completed', links={'status': f"/users/async_check/{task_id}"})
    
# main microservice run
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)