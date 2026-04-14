import json
import unittest
from unittest.mock import Mock, patch

import upload


class UploadHelpersTests(unittest.TestCase):
    def test_build_notification_with_email_and_webhook(self) -> None:
        data = json.loads(
            upload.build_notification("user@example.com", "https://hooks.example.com/callback")
        )
        self.assertEqual(
            data,
            [
                {"type": "email", "entry": "user@example.com"},
                {"type": "webhook", "entry": "https://hooks.example.com/callback"},
            ],
        )

    def test_build_notification_requires_target(self) -> None:
        with self.assertRaises(ValueError):
            upload.build_notification(None, None)

    def test_build_deal_payload_omits_none_values(self) -> None:
        payload = upload.build_deal_payload("Sunset Plaza", city="Austin", unit_count=128)
        self.assertEqual(
            payload,
            {"dealName": "Sunset Plaza", "city": "Austin", "unitCount": 128},
        )

    def test_terminal_statuses(self) -> None:
        self.assertTrue(upload.is_terminal_status("complete"))
        self.assertTrue(upload.is_terminal_status("partially complete"))
        self.assertTrue(upload.is_terminal_status("failed"))
        self.assertFalse(upload.is_terminal_status("queued"))


class RequestTests(unittest.TestCase):
    def make_response(self, status_code: int, body: dict) -> Mock:
        response = Mock()
        response.status_code = status_code
        response.json.return_value = body
        response.text = json.dumps(body)
        return response

    @patch("upload.requests.request")
    def test_api_request_success(self, mock_request: Mock) -> None:
        mock_request.return_value = self.make_response(200, {"data": {"ok": True}})
        body = upload.api_request("key", "GET", "/test", expected_status=200)
        self.assertEqual(body, {"data": {"ok": True}})

    @patch("upload.requests.request")
    def test_api_request_failure_raises(self, mock_request: Mock) -> None:
        mock_request.return_value = self.make_response(400, {"error": "bad request"})
        with self.assertRaises(RuntimeError):
            upload.api_request("key", "GET", "/test", expected_status=200)

    @patch("upload.requests.request")
    def test_create_deal(self, mock_request: Mock) -> None:
        mock_request.return_value = self.make_response(
            201, {"data": {"counterId": 42, "dealName": "Sunset Plaza"}}
        )
        result = upload.create_deal("key", deal_name="Sunset Plaza")
        self.assertEqual(result["counterId"], 42)
        kwargs = mock_request.call_args.kwargs
        self.assertEqual(kwargs["json"]["dealName"], "Sunset Plaza")

    @patch("upload.requests.request")
    def test_list_deals(self, mock_request: Mock) -> None:
        mock_request.return_value = self.make_response(
            200,
            {"data": {"deals": [{"counterId": 42, "dealName": "Sunset Plaza"}], "total": 1}},
        )
        result = upload.list_deals("key", search="Sunset")
        self.assertEqual(result["total"], 1)
        kwargs = mock_request.call_args.kwargs
        self.assertEqual(kwargs["params"]["search"], "Sunset")

    @patch("upload.requests.request")
    def test_get_deal(self, mock_request: Mock) -> None:
        mock_request.return_value = self.make_response(
            200, {"data": {"counterId": 42, "dealName": "Sunset Plaza"}}
        )
        result = upload.get_deal("key", 42)
        self.assertEqual(result["dealName"], "Sunset Plaza")

    @patch("upload.requests.request")
    def test_update_deal(self, mock_request: Mock) -> None:
        mock_request.return_value = self.make_response(
            200, {"data": {"counterId": 42, "dealName": "Updated Deal"}}
        )
        result = upload.update_deal("key", 42, deal_name="Updated Deal")
        self.assertEqual(result["dealName"], "Updated Deal")
        kwargs = mock_request.call_args.kwargs
        self.assertEqual(kwargs["json"]["dealName"], "Updated Deal")

    @patch("upload.requests.request")
    def test_delete_deal(self, mock_request: Mock) -> None:
        mock_request.return_value = self.make_response(
            200, {"data": {"message": "Deal 42 deleted successfully"}}
        )
        result = upload.delete_deal("key", 42)
        self.assertIn("message", result)

    def test_update_deal_requires_payload(self) -> None:
        with self.assertRaises(ValueError):
            upload.update_deal("key", 42)

    @patch("upload.requests.request")
    def test_status_request(self, mock_request: Mock) -> None:
        mock_request.return_value = self.make_response(200, {"data": {"status": "queued"}})
        result = upload.status_request("key", "batch-1")
        self.assertEqual(result["status"], "queued")


if __name__ == "__main__":
    unittest.main()
