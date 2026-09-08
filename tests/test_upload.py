import pytest
from httpx import ASGITransport, AsyncClient
from mock_api_py.store import DataStore
from mock_api_py.server import create_app


@pytest.mark.anyio
async def test_file_upload_and_static_serving(tmp_path):
    upload_dir = tmp_path / "test_uploads"
    store = DataStore(initial_data={"items": []})
    app = create_app(store, upload_dir=str(upload_dir))

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        file_content = b"Hello, this is a mock upload test file!"
        files = {
            "file": ("sample.txt", file_content, "text/plain")
        }
        res = await ac.post("/upload", files=files)
        assert res.status_code == 200
        data = res.json()
        assert data["filename"] == "sample.txt"
        assert data["size"] == len(file_content)
        assert data["url"] == "/uploads/sample.txt"
        assert data["contentType"] == "text/plain"

        # Verify file can be retrieved via /uploads/
        get_res = await ac.get(data["url"])
        assert get_res.status_code == 200
        assert get_res.content == file_content


@pytest.mark.anyio
async def test_file_upload_collision_disambiguation(tmp_path):
    upload_dir = tmp_path / "test_uploads_collision"
    store = DataStore(initial_data={"items": []})
    app = create_app(store, upload_dir=str(upload_dir))

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        files1 = {"file": ("avatar.png", b"image1", "image/png")}
        res1 = await ac.post("/upload", files=files1)
        assert res1.status_code == 200
        data1 = res1.json()
        assert data1["filename"] == "avatar.png"

        files2 = {"file": ("avatar.png", b"image2", "image/png")}
        res2 = await ac.post("/upload", files=files2)
        assert res2.status_code == 200
        data2 = res2.json()
        assert data2["filename"] != "avatar.png"
        assert data2["filename"].startswith("avatar_")
        assert data2["filename"].endswith(".png")
