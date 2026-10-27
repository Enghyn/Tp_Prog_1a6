from app.core.paginacion import PageParams, Page


def test_page_params_defaults():
    params = PageParams()
    assert params.page == 1
    assert params.size == 10


def test_page_params_validation():
    params = PageParams(page=2, size=50)
    assert params.page == 2
    assert params.size == 50


def test_page_serialization():
    page = Page(items=[{"id": 1}], total=1, page=1, size=10)
    data = page.model_dump()
    assert data["items"] == [{"id": 1}]
    assert data["total"] == 1
    assert data["page"] == 1
    assert data["size"] == 10
