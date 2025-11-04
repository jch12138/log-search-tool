from app.services.utils.filename_resolver import resolve_log_filename, validate_log_filename_pattern

def test_validate_pattern_ok():
    ok, errors = validate_log_filename_pattern('app-{YYYY}-{MM}-{DD}-{N}.log')
    assert ok and not errors

def test_resolve_without_N(monkeypatch):
    pattern = 'app-{YYYY}.log'
    filename = resolve_log_filename(pattern)
    assert 'app-' in filename and filename.endswith('.log')
