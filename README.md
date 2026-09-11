# Blog Management API

A mini blogging system built using FastAPI, SQLAlchemy, SQLite and JWT authentication.

## Features

- User registration and login
- JWT authentication
- Password hashing
- Create, read, update and delete posts
- Post ownership validation
- Public post viewing
- Comments
- Likes and unlikes
- Duplicate like prevention
- Email notifications for comments and likes
- Swagger API documentation

## Run the Project

```bash
uvicorn app.main:app --reload