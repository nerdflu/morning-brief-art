"""One approved manual Flare pilot; no scheduler or production image publication."""
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.error
import urllib.request
from PIL import Image

MODEL = "gpt-image-2.5-flare"
ALLOWED_MODELS = {MODEL, "gpt-image-2.5-flare-2026-09-08"}
TEST_ID = "flare-access-2026-10-26"
LEDGER = Path(".pipeline-tests") / (TEST_ID + ".json")
PROMPT = "Black ink illustration of a lighthouse above calm waves. White background, bold simple lines, no text, no people."
PARAMETERS = {"model": MODEL, "prompt": PROMPT, "n": 1, "quality": "low", "size": "1024x1024", "output_format": "png"}
MAX_RESPONSE_BYTES = 20_000_000


class PilotError(Exception):
    pass


class ApiError(PilotError):
    def __init__(self, status):
        self.status = status
        super().__init__("api_http_" + str(status))


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class OpenAITransport:
    def __init__(self, key):
        self.key = key
        self.opener = urllib.request.build_opener(NoRedirect())

    def call(self, path, body=None):
        if path not in ("/models/" + MODEL, "/images/generations"):
            raise PilotError("unsupported_endpoint")
        headers = {"Authorization": "Bearer " + self.key, "Content-Type": "application/json"}
        request = urllib.request.Request("https://api.openai.com/v1" + path, headers=headers,
                                         data=json.dumps(body).encode() if body is not None else None)
        try:
            with self.opener.open(request, timeout=180) as response:
                raw = response.read(MAX_RESPONSE_BYTES + 1)
                if len(raw) > MAX_RESPONSE_BYTES:
                    raise PilotError("response_too_large")
                return json.loads(raw), response.headers.get("x-request-id")
        except urllib.error.HTTPError as error:
            # Never log response bodies, request headers or the credential.
            raise ApiError(error.code) from None


def usage_cost(usage):
    if not isinstance(usage, dict):
        raise PilotError("usage_missing")
    counts = {}
    for key in ("input_tokens", "output_tokens"):
        value = usage.get(key)
        if type(value) is not int or value < 0:
            raise PilotError("usage_invalid")
        counts[key] = value
    details = usage.get("input_tokens_details", {})
    if not isinstance(details, dict) or details.get("image_tokens", 0) != 0:
        raise PilotError("unexpected_image_input_usage")
    # Text-only direct Images request: no cached-input discounts assumed.
    usd = (counts["input_tokens"] * 5 + counts["output_tokens"] * 30) / 1_000_000
    return counts, round(usd, 8)


def validate_result(response):
    if not isinstance(response, dict) or response.get("model", MODEL) not in ALLOWED_MODELS:
        raise PilotError("unexpected_model")
    if not isinstance(response.get("data"), list) or len(response["data"]) != 1:
        raise PilotError("unexpected_image_count")
    try:
        raw = base64.b64decode(response["data"][0]["b64_json"], validate=True)
        image = Image.open(io.BytesIO(raw))
        image.load()
    except Exception:
        raise PilotError("invalid_image") from None
    if image.format != "PNG" or image.size != (1024, 1024):
        raise PilotError("unexpected_dimensions_or_format")
    counts, usd = usage_cost(response.get("usage"))
    if counts["input_tokens"] > 512 or counts["output_tokens"] > 4096 or usd > 0.25:
        raise PilotError("unexpected_usage_or_cost")
    return raw, {"width": image.width, "height": image.height, "sha256": hashlib.sha256(raw).hexdigest(),
                 "usage": counts, "estimated_cost_usd": usd,
                 "cost_basis": "Flare standard text input $5/M; image output $30/M; excludes FX/fees/tax"}


def run_pilot(root, transport, persist, run_id, attempt):
    if str(attempt) != "1":
        raise PilotError("rerun_not_allowed")
    if (root / LEDGER).exists():
        raise PilotError("approved_test_already_reserved_no_second_paid_call")
    model, _ = transport.call("/models/" + MODEL)
    if not isinstance(model, dict) or model.get("id") not in ALLOWED_MODELS:
        raise PilotError("model_metadata_mismatch")
    state = {"test_id": TEST_ID, "run_id": str(run_id), "state": "reserved", "model": MODEL,
             "quality": "low", "size": "1024x1024", "n": 1, "monthly_allowance_aud": 5,
             "reserved_aud": 5, "paid_requests_submitted": 0, "metadata_visible": True,
             "note": "Entire allowance reserved; no automatic release, retry or further paid generation."}
    persist(state)  # Must be durable before any paid request.
    state = {**state, "state": "submitted", "paid_requests_submitted": 1}
    persist(state)  # If this fails, the API is never invoked.
    try:
        response, request_id = transport.call("/images/generations", dict(PARAMETERS))
    except ApiError as error:
        state.update(state="rejected_or_uncertain", http_status=error.status)
        persist(state)
        raise
    except Exception:
        state.update(state="uncertain", reason="request_outcome_unknown_do_not_retry")
        persist(state)
        raise PilotError("request_outcome_unknown_do_not_retry") from None
    try:
        raw, result = validate_result(response)
    except PilotError as error:
        state.update(state="needs_review", reason=str(error))
        if isinstance(response, dict):
            try:
                counts, usd = usage_cost(response.get("usage"))
                state.update(usage=counts, estimated_cost_usd=usd)
            except PilotError:
                pass
        persist(state)
        raise
    artifacts = root / "test-artifacts"
    artifacts.mkdir(exist_ok=True)
    (artifacts / "flare-test.png").write_bytes(raw)
    state.update(state="complete", **result)
    if isinstance(request_id, str) and len(request_id) < 120 and request_id.replace("_", "").replace("-", "").isalnum():
        state["request_id"] = request_id
    persist(state)
    (artifacts / "result.json").write_text(json.dumps(state, indent=2) + "\n")
    return state


def git_persist(root, state):
    path = root / LEDGER
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(state, indent=2) + "\n")
    commands = [["git", "add", str(LEDGER)], ["git", "-c", "user.name=github-actions[bot]",
                 "-c", "user.email=41898282+github-actions[bot]@users.noreply.github.com",
                 "commit", "-m", "Record approved Flare pilot state: " + state["state"]],
                ["git", "push", "origin", "HEAD:main"]]
    for command in commands:
        result = subprocess.run(command, cwd=root, capture_output=True)
        if result.returncode:
            raise PilotError("ledger_persistence_failed_no_automatic_retry")


def main():
    if os.environ.get("GITHUB_REPOSITORY") != "nerdflu/morning-brief-art" or os.environ.get("GITHUB_REF") != "refs/heads/main":
        raise PilotError("wrong_repository_or_ref")
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        raise PilotError("missing_actions_secret")
    root = Path.cwd()
    result = run_pilot(root, OpenAITransport(key), lambda state: git_persist(root, state),
                       os.environ.get("GITHUB_RUN_ID", ""), os.environ.get("GITHUB_RUN_ATTEMPT", ""))
    print(json.dumps(result, sort_keys=True))
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as output:
            output.write("## Approved Flare pilot\n\n```json\n" + json.dumps(result, indent=2) + "\n```\n")


if __name__ == "__main__":
    try:
        main()
    except PilotError as error:
        print(json.dumps({"status": "stopped", "reason": str(error)}))
        sys.exit(1)
    except Exception:
        print(json.dumps({"status": "stopped", "reason": "unexpected_error_no_automatic_retry"}))
        sys.exit(1)
