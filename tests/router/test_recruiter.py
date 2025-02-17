import pytest
from httpx import AsyncClient
from faker import Faker
import pytest_asyncio
from conftest import transport, TestingSessionLocal
from db.models import User, Recruiter
from auth.password import hash_password

fake = Faker()


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio(loop_scope="session")
async def test_create_recruiter_success(client):
    username = fake.user_name()
    email = fake.email()
    password = fake.password()
    first_name = fake.first_name()
    last_name = fake.last_name()
    print(
        f"Test data: username:  {username}, email  {email}, {password}, {first_name}, {last_name}"
    )

    test_payload = {
        "username": username,
        "email": email,
        "password": password,
        "first_name": first_name,
        "last_name": last_name,
    }

    response = await client.post("/recruiters", json=test_payload)

    assert response.status_code == 200

    data = response.json()
    print(f"Response data: {data}")
    assert data["username"] == username
    assert data["email"] == email
    assert data["first_name"] == first_name
    assert data["last_name"] == last_name

    assert "user_id" in data
    assert "recruiter_id" in data


async def create_random_recruiter() -> tuple[str, str]:
    username = fake.user_name()
    email = fake.email()
    password = fake.password()
    first_name = fake.first_name()
    last_name = fake.last_name()
    async with TestingSessionLocal() as session:
        user = User(
            username=username,
            email=email,
            password=hash_password(password),
        )
        session.add(user)
        await session.flush()
        recruiter = Recruiter(
            user_id=user.id,
            first_name=first_name,
            last_name=last_name,
        )
        session.add(recruiter)
        await session.commit()

    return username, password


@pytest.mark.asyncio(loop_scope="session")
async def test_login_recruiter_success(client):
    username, password = await create_random_recruiter()

    test_payload = {
        "username": username,
        "password": password,
    }

    response = await client.post("/recruiters/login", json=test_payload)

    print(f"Response data: {response.json()}")
    assert response.status_code == 200
    assert "access_token" in response.json()
    assert "refresh_token" in response.json()


@pytest.mark.asyncio(loop_scope="session")
async def test_get_recruiter_profile(client):
    username, password = await create_random_recruiter()

    test_payload = {
        "username": username,
        "password": password,
    }

    response = await client.post("/recruiters/login", json=test_payload)
    assert response.status_code == 200
    data = response.json()
    access_token = data["access_token"]

    response = await client.get(
        "/recruiters/profile", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    print(f"Response data: {data}")
    assert "user_id" in data
    assert "recruiter_id" in data
