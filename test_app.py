import unittest
from unittest.mock import patch, MagicMock
import app

class TestExtractTextFromFile(unittest.TestCase):
    def test_txt_format(self):
        """Test extraction from a plain text file."""
        text_content = b"Hello, this is a plain text file."
        result = app.extract_text_from_file("test.txt", text_content)
        self.assertEqual(result, "Hello, this is a plain text file.")

    def test_pdf_format(self):
        """Test extraction from a PDF file using mocked PdfReader."""
        mock_pdf = MagicMock()
        mock_page_1 = MagicMock()
        mock_page_1.extract_text.return_value = "Hello from page 1."
        mock_page_2 = MagicMock()
        mock_page_2.extract_text.return_value = "Hello from page 2."
        mock_pdf.pages = [mock_page_1, mock_page_2]
        
        with patch('pypdf.PdfReader', return_value=mock_pdf) as mock_reader:
            result = app.extract_text_from_file("document.pdf", b"dummy_pdf_bytes")
            mock_reader.assert_called_once()
            self.assertEqual(result, "Hello from page 1.\nHello from page 2.")

    def test_docx_format(self):
        """Test extraction from a DOCX file using mocked docx.Document."""
        mock_doc = MagicMock()
        mock_para_1 = MagicMock()
        mock_para_1.text = "First paragraph."
        mock_para_2 = MagicMock()
        mock_para_2.text = "Second paragraph."
        mock_doc.paragraphs = [mock_para_1, mock_para_2]
        
        with patch('docx.Document', return_value=mock_doc) as mock_document_loader:
            result = app.extract_text_from_file("document.docx", b"dummy_docx_bytes")
            mock_document_loader.assert_called_once()
            self.assertEqual(result, "First paragraph.\nSecond paragraph.")

    def test_unsupported_format(self):
        """Test behavior when an unsupported file format is passed."""
        # Test with an image extension (unsupported by this specific parser)
        result_png = app.extract_text_from_file("image.png", b"dummy_bytes")
        self.assertIn("⚠️ Unsupported format: png", result_png)

        # Test with other unsupported document extensions
        result_csv = app.extract_text_from_file("data.csv", b"col1,col2\n1,2")
        self.assertIn("⚠️ Unsupported format: csv", result_csv)

        result_md = app.extract_text_from_file("notes.md", b"# Markdown Header")
        self.assertIn("⚠️ Unsupported format: md", result_md)

    def test_exception_handling(self):
        """Test that exceptions raised during parsing are handled and returned as error messages."""
        with patch('pypdf.PdfReader', side_effect=Exception("Corrupt PDF file")):
            result = app.extract_text_from_file("corrupt.pdf", b"corrupt_bytes")
            self.assertIn("Error reading corrupt.pdf: Corrupt PDF file", result)

class TestFindUrls(unittest.TestCase):
    def test_no_urls(self):
        """Test with input containing no URLs."""
        self.assertEqual(app.find_urls("No URLs here."), [])

    def test_single_http_url(self):
        """Test with input containing a single http URL."""
        self.assertEqual(app.find_urls("Check out http://example.com/page"), ["http://example.com/page"])

    def test_single_https_url(self):
        """Test with input containing a single https URL."""
        self.assertEqual(app.find_urls("Go to https://google.com for info."), ["https://google.com"])

    def test_multiple_urls(self):
        """Test with input containing multiple HTTP and HTTPS URLs."""
        text = "Visit https://site.com/foo and http://another.net/bar?query=1"
        self.assertEqual(app.find_urls(text), ["https://site.com/foo", "http://another.net/bar?query=1"])

    def test_url_with_delimiters(self):
        """Test with URLs bounded by HTML quotes or single quotes to ensure delimiters are stripped."""
        text = 'Look at <a href="https://example.com">site</a> or \'https://test.org\''
        self.assertEqual(app.find_urls(text), ["https://example.com", "https://test.org"])

class TestIsSafeUrl(unittest.TestCase):
    def test_safe_public_urls(self):
        """Test is_safe_url with public URLs."""
        self.assertTrue(app.is_safe_url("https://google.com"))
        self.assertTrue(app.is_safe_url("http://example.com/some/path?param=value"))

    def test_unsafe_local_urls(self):
        """Test is_safe_url with private/local URLs that should be blocked."""
        self.assertFalse(app.is_safe_url("http://localhost"))
        self.assertFalse(app.is_safe_url("http://127.0.0.1"))
        self.assertFalse(app.is_safe_url("http://[::1]"))
        self.assertFalse(app.is_safe_url("http://192.168.1.1"))
        self.assertFalse(app.is_safe_url("http://10.0.0.1"))
        self.assertFalse(app.is_safe_url("http://169.254.169.254"))

    def test_invalid_urls(self):
        """Test is_safe_url with invalid schemes or formats."""
        self.assertFalse(app.is_safe_url("ftp://example.com"))
        self.assertFalse(app.is_safe_url("not-a-url"))

class TestScrapeWebsite(unittest.TestCase):
    @patch('requests.get')
    def test_scrape_success(self, mock_get):
        """Test scrape_website with a successful HTTP response."""
        mock_response = MagicMock()
        mock_response.content = b"<html><body><script>alert(1)</script><p>Hello World</p></body></html>"
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        # Use a safe public URL unique to this test
        result = app.scrape_website("https://success.com")
        self.assertEqual(result, "Hello World")
        mock_get.assert_called_once()

    @patch('requests.get')
    def test_scrape_request_exception(self, mock_get):
        """Test scrape_website handling a RequestException."""
        import requests
        mock_get.side_effect = requests.exceptions.RequestException("Connection error")

        # Use a safe public URL unique to this test
        result = app.scrape_website("https://exception.com")
        self.assertIn("Error scraping https://exception.com: Connection error", result)

    @patch('requests.get')
    def test_scrape_http_error(self, mock_get):
        """Test scrape_website when raise_for_status raises an HTTPError."""
        import requests
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("404 Client Error")
        mock_get.return_value = mock_response

        # Use a safe public URL unique to this test
        result = app.scrape_website("https://httperror.com")
        self.assertIn("Error scraping https://httperror.com: 404 Client Error", result)

    def test_scrape_unsafe_url(self):
        """Test that scrape_website blocks unsafe URLs immediately."""
        result = app.scrape_website("http://127.0.0.1:8501")
        self.assertIn("⚠️ SSRF Protection", result)

if __name__ == '__main__':
    unittest.main()



