from src.mcp.errors import HorizonMcpError


def test_horizon_mcp_error_string_representation() -> None:
    err = HorizonMcpError(code="E_TEST", message="boom", details={"k": "v"})

    assert str(err) == "E_TEST: boom"
    assert err.details == {"k": "v"}
