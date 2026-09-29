"""Web Service Provider with SSRF protections."""

import ipaddress
import logging
import urllib.parse
from socket import gethostbyname
from typing import Any, Protocol, List, Dict
import httpx
from bs4 import BeautifulSoup
from app.core.config import settings

logger = logging.getLogger(__name__)

def is_safe_url(url: str) -> bool:
    """Validate URL against SSRF and local access."""
    try:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ["http", "https"]:
            return False
            
        hostname = parsed.hostname
        if not hostname:
            return False
            
        # Try resolving the hostname to check if it points to a local/private IP
        # In a strict production setting, this should be done natively within the HTTP client
        # connection pool to prevent DNS rebinding attacks (time-of-check to time-of-use).
        try:
            ip = gethostbyname(hostname)
            ip_obj = ipaddress.ip_address(ip)
            
            # Check for private, loopback, link-local, multicast, etc.
            if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local or ip_obj.is_multicast:
                logger.warning(f"SSRF Protection blocked IP: {ip} for URL: {url}")
                return False
                
        except Exception as e:
            logger.warning(f"Could not resolve hostname {hostname}: {e}")
            return False

        return True
    except Exception:
        return False

class WebProvider(Protocol):
    async def search(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        ...
        
    async def fetch(self, url: str) -> str:
        ...

class SandboxWebProvider:
    """A safe, sandbox web provider using DuckDuckGo HTML for search."""
    
    async def search(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        # This is a very basic sandbox search that uses DuckDuckGo HTML (no API key).
        # In production, use Bing Search API or Google Programmable Search.
        url = "https://html.duckduckgo.com/html/"
        data = {"q": query}
        
        async with httpx.AsyncClient(timeout=10.0, headers={"User-Agent": "Mozilla/5.0"}) as client:
            try:
                response = await client.post(url, data=data)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, "html.parser")
                results = []
                
                for a in soup.find_all('a', class_='result__url'):
                    if len(results) >= max_results:
                        break
                    
                    link = a.get('href')
                    if link and link.startswith('//duckduckgo.com/l/?uddg='):
                        # Extract the actual URL
                        parsed = urllib.parse.parse_qs(urllib.parse.urlparse(link).query)
                        if 'uddg' in parsed:
                            actual_url = parsed['uddg'][0]
                            # Find snippet
                            parent = a.find_parent('div', class_='result')
                            snippet_elem = parent.find('a', class_='result__snippet') if parent else None
                            snippet = snippet_elem.text if snippet_elem else ""
                            
                            results.append({
                                "title": a.text.strip(),
                                "url": actual_url,
                                "snippet": snippet.strip(),
                                "source": urllib.parse.urlparse(actual_url).netloc
                            })
                return results
            except Exception as e:
                logger.error(f"Sandbox web search failed: {e}")
                return []

    async def fetch(self, url: str) -> str:
        """Fetch URL content securely, extracting text only."""
        if not is_safe_url(url):
            raise ValueError("URL blocked by security policy (SSRF protection)")
            
        # We manually disable following redirects indefinitely and track size
        limits = httpx.Limits(max_keepalive_connections=5, max_connections=10)
        
        async with httpx.AsyncClient(
            timeout=10.0, 
            limits=limits, 
            follow_redirects=True, # We will follow, but we can't easily validate IPs of redirects mid-flight with httpx 
                                   # without a custom transport. For this sandbox, we just rely on standard httpx limits 
                                   # and the initial IP check.
            max_redirects=settings.web_max_redirects
        ) as client:
            # First, check content length if provided
            try:
                # Use a streaming response to prevent downloading huge files
                async with client.stream("GET", url, headers={"User-Agent": "Mozilla/5.0"}) as response:
                    response.raise_for_status()
                    
                    content_type = response.headers.get("Content-Type", "")
                    if "text/html" not in content_type and "text/plain" not in content_type and "application/json" not in content_type:
                        raise ValueError(f"Unsupported content type: {content_type}")
                    
                    body = b""
                    async for chunk in response.aiter_bytes():
                        body += chunk
                        if len(body) > settings.web_max_fetch_bytes:
                            logger.warning(f"Truncating fetch for {url} at {settings.web_max_fetch_bytes} bytes")
                            break
                            
                    text_content = body.decode('utf-8', errors='ignore')
                    
                    if "text/html" in content_type:
                        # Strip HTML
                        soup = BeautifulSoup(text_content, "html.parser")
                        # Remove script and style elements
                        for script in soup(["script", "style"]):
                            script.decompose()
                        # Get text
                        text = soup.get_text(separator=' ', strip=True)
                        return text
                    else:
                        return text_content
                        
            except httpx.HTTPError as e:
                logger.error(f"HTTP fetch failed for {url}: {e}")
                raise ValueError(f"Failed to fetch content from {url}")

def get_web_provider() -> WebProvider:
    # Always use sandbox for this stage
    return SandboxWebProvider()
