from app.models import SearchParams
import pytest

def test_search_params_validate_ok():
    sp = SearchParams(keyword='error')
    sp.validate()  # should not raise

def test_search_params_invalid_context():
    sp = SearchParams(context_span=100)
    with pytest.raises(ValueError):
        sp.validate()
