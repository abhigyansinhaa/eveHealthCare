import re
import subprocess
from pathlib import Path

import pytest
from httpx import AsyncClient

STATIC_FILE = Path(__file__).parent.parent / "app" / "static" / "index.html"


@pytest.mark.asyncio
class TestFrontendDashboard:
    """Smoke tests for frontend route serving."""

    async def test_root_serves_html(self, client: AsyncClient):
        response = await client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "EVE HealthCare" in response.text
        assert "Diagnostic Portal" in response.text

    async def test_dashboard_serves_html(self, client: AsyncClient):
        response = await client.get("/dashboard")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "EVE HealthCare" in response.text


class TestFrontendLint:
    """Automated lint tests for frontend HTML, CSS, JavaScript, and DOM integrity."""

    @pytest.fixture(autouse=True)
    def load_html(self):
        assert STATIC_FILE.exists(), f"Frontend file {STATIC_FILE} does not exist"
        self.html = STATIC_FILE.read_text(encoding="utf-8")

    def test_doctype_and_html_structure(self):
        """Verify valid DOCTYPE and core document tags."""
        assert self.html.strip().lower().startswith("<!doctype html>"), "Missing or invalid <!DOCTYPE html>"
        
        for tag in ["html", "head", "body", "title"]:
            open_count = len(re.findall(rf"<{tag}(\s+[^>]*)?>", self.html, re.IGNORECASE))
            close_count = len(re.findall(rf"</{tag}>", self.html, re.IGNORECASE))
            assert open_count >= 1, f"Missing opening <{tag}> tag"
            assert close_count >= 1, f"Missing closing </{tag}> tag"
            assert open_count == close_count, f"Mismatched <{tag}> tags: {open_count} opened vs {close_count} closed"

    def test_dom_element_ids_unique(self):
        """Ensure all HTML element IDs are globally unique."""
        ids = re.findall(r'\sid=["\']([^"\']+)["\']', self.html, re.IGNORECASE)
        assert len(ids) > 0, "No element IDs found in frontend HTML"
        seen = set()
        duplicates = set()
        for el_id in ids:
            if el_id in seen:
                duplicates.add(el_id)
            seen.add(el_id)
        assert not duplicates, f"Duplicate element IDs found: {duplicates}"

    def test_critical_ui_elements_exist(self):
        """Verify presence of key interactive dashboard components."""
        required_elements = [
            "tab-centres",
            "tab-bookings",
            "tab-simulator",
            "authModal",
            "createCentreModal",
            "addTestModal",
            "toast-container",
            "authEmail",
            "authPassword",
            "simBookingId",
        ]
        for elem_id in required_elements:
            assert f'id="{elem_id}"' in self.html, f"Required UI element ID '{elem_id}' not found in frontend"

    def test_css_blocks_balanced(self):
        """Validate CSS syntax for balanced braces."""
        style_blocks = re.findall(r"<style[^>]*>([\s\S]*?)</style>", self.html, re.IGNORECASE)
        assert len(style_blocks) > 0, "No <style> blocks found in frontend HTML"
        for idx, css in enumerate(style_blocks, 1):
            open_braces = css.count("{")
            close_braces = css.count("}")
            assert open_braces > 0, f"Style block #{idx} is empty or has no CSS rules"
            assert open_braces == close_braces, f"Style block #{idx} unbalanced: {open_braces} '{{' vs {close_braces} '}}'"

    def test_inline_javascript_syntax_via_node(self):
        """Extract inline JS and validate syntax using Node.js."""
        scripts = re.findall(r"<script(?![^>]*src=)[^>]*>([\s\S]*?)</script>", self.html, re.IGNORECASE)
        assert len(scripts) > 0, "No inline <script> block found in frontend HTML"
        for idx, script_content in enumerate(scripts, 1):
            assert len(script_content.strip()) > 100, f"Script block #{idx} appears empty"
            # Validate JS syntax using node --input-type=module --check or Function check
            result = subprocess.run(
                ["node", "-e", "new Function(process.argv[1]);", script_content],
                capture_output=True,
                text=True,
            )
            assert result.returncode == 0, f"Script block #{idx} syntax error: {result.stderr}"

    def test_api_endpoints_consistency(self):
        """Verify frontend references the required backend API endpoints."""
        required_endpoints = [
            "/auth/signup",
            "/auth/login",
            "/centres",
            "/bookings",
            "/payments",
        ]
        for endpoint in required_endpoints:
            assert endpoint in self.html, f"Expected endpoint '{endpoint}' not referenced in frontend code"
