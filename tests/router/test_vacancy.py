import pytest
from test_recruiter import create_random_recruiter
import pytest_asyncio
from httpx import AsyncClient
from faker import Faker
from conftest import transport
from datetime import datetime

fake = Faker()


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio(loop_scope="session")
async def test_create_vacancy(client):
    username, password = await create_random_recruiter()

    test_payload = {
        "username": username,
        "password": password,
    }

    response = await client.post("/recruiters/login", json=test_payload)
    assert response.status_code == 200
    data = response.json()

    # Debugging the access token
    assert "access_token" in data, "Access token is missing"
    print(f"Access token: {data['access_token']}")

    end_date = datetime(2025, 12, 31).isoformat()  # Ensuring valid date format

    response = await client.post(
        "/vacancies", 
        json={
            "title": fake.job(),
            "description": fake.text(),
            "location": fake.city(),
            "end_date": end_date,  # Correct date format
        }, 
        headers={"Authorization": f"Bearer {data['access_token']}"}
    )

    if response.status_code != 200:
        print(f"Error: {response.status_code} - {response.text}")

    assert response.status_code == 200
    data = response.json()
    print(f"Response data: {data}")

    assert "id" in data
    assert "recruiter_id" in data
    assert "title" in data
    assert "description" in data
    assert "location" in data
    assert "is_active" in data
    assert "created_at" in data
    assert "end_date" in data

