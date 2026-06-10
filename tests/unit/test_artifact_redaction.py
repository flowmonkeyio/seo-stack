from stackos.artifacts.redaction import redact_secret_text, redact_secrets


def test_redact_secrets_redacts_signed_url_values_in_nested_strings() -> None:
    payload = {
        "media": {
            "first_frame_url": (
                "https://cdn.example.com/input.png?X-Amz-Credential=abc&"
                "X-Amz-Signature=def&Expires=9999999999&safe=value"
            )
        }
    }

    redacted = redact_secrets(payload)

    assert redacted["media"]["first_frame_url"] == (
        "https://cdn.example.com/input.png?X-Amz-Credential=[redacted]&"
        "X-Amz-Signature=[redacted]&Expires=[redacted]&safe=value"
    )


def test_redact_secret_text_redacts_short_signature_query_params() -> None:
    assert redact_secret_text("https://example.test/file.mp4?sig=abc123") == (
        "https://example.test/file.mp4?sig=[redacted]"
    )
