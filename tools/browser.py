"""
Generic Browser Tool Layer for InvoicePilot.
Wraps Playwright sync API to provide element tagging, page inspection,
clicks, text typing, date formatting, and screenshot capabilities.
Contains NO application-specific logic.
"""

import os
import re
from datetime import datetime
from typing import Dict, Any, Optional
from playwright.sync_api import sync_playwright, Playwright, Browser, BrowserContext, Page, TimeoutError as PlaywrightTimeoutError, Error as PlaywrightError


class BrowserTools:
    """
    Generic browser operations wrapper for AI worker interaction.
    Guarantees structured dictionary responses and never raises unhandled exceptions.
    """

    def __init__(self, headless: bool = False, slow_mo: int = 300):
        """Initialize Playwright sync instance and launch Chromium browser."""
        self._playwright: Playwright = sync_playwright().start()
        self._browser: Browser = self._playwright.chromium.launch(headless=headless, slow_mo=slow_mo)
        self._context: BrowserContext = self._browser.new_context()
        self.page: Page = self._context.new_page()

    def _wrap_result(self, ok: bool, observation: str, error: Optional[str] = None) -> Dict[str, Any]:
        """Format uniform return dictionary for all tool methods."""
        return {
            "ok": ok,
            "observation": observation,
            "error": error
        }

    def goto(self, url: str) -> Dict[str, Any]:
        """
        Navigate browser to the specified URL.
        Catches timeouts, network errors, and HTTP 4xx/5xx status codes.
        """
        try:
            response = self.page.goto(url, wait_until="domcontentloaded", timeout=10000)
            if response and response.status >= 400:
                msg = f"HTTP {response.status} from {url}"
                return self._wrap_result(
                    ok=False,
                    observation=f"Navigation failed: {msg}",
                    error=msg
                )
            return self._wrap_result(
                ok=True,
                observation=f"Successfully navigated to {self.page.url} (Title: '{self.page.title()}')"
            )
        except PlaywrightTimeoutError:
            err = f"Navigation to {url} timed out after 10s."
            return self._wrap_result(ok=False, observation=err, error=err)
        except Exception as e:
            err = f"Navigation error: {str(e)}"
            return self._wrap_result(ok=False, observation=err, error=err)

    def read_page(self) -> Dict[str, Any]:
        """
        Inspect current DOM state:
        1. Tags all visible interactive elements with incremental `data-agent-id` attributes via JS.
        2. Extracts URL, Title, trimmed visible body text, and interactive element metadata.
        3. Returns structured observation.
        """
        try:
            js_script = """
            () => {
                // Remove existing agent tags
                document.querySelectorAll('[data-agent-id]').forEach(el => el.removeAttribute('data-agent-id'));
                
                // Helper function to get text of an associated <label>
                function getAssociatedLabelText(el) {
                    let labelEl = null;
                    if (el.id) {
                        try {
                            labelEl = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
                        } catch (e) {
                            labelEl = document.querySelector(`label[for="${el.id}"]`);
                        }
                    }
                    if (!labelEl) {
                        labelEl = el.closest('label');
                    }
                    if (labelEl) {
                        const clone = labelEl.cloneNode(true);
                        clone.querySelectorAll('input, select, textarea, button').forEach(child => child.remove());
                        return (clone.innerText || clone.textContent || '').trim();
                    }
                    return '';
                }

                // Find all potential interactive elements
                const candidates = Array.from(document.querySelectorAll('a, button, input, select, textarea'));
                let idCounter = 1;
                const elements = [];
                
                candidates.forEach(el => {
                    // Filter visible elements
                    const rect = el.getBoundingClientRect();
                    const isVisible = rect.width > 0 && rect.height > 0 && 
                                      window.getComputedStyle(el).visibility !== 'hidden' && 
                                      window.getComputedStyle(el).display !== 'none';
                    
                    if (isVisible) {
                        const elementId = idCounter++;
                        el.setAttribute('data-agent-id', elementId.toString());
                        
                        const tagName = el.tagName.toLowerCase();
                        let elType = tagName;
                        if (tagName === 'input') {
                            elType = `input:${el.type || 'text'}`;
                        }
                        
                        let label = '';
                        let href = null;
                        let placeholder = null;
                        let value = null;
                        let options = null;

                        if (tagName === 'a') {
                            label = (el.innerText || el.textContent || el.getAttribute('aria-label') || '').trim();
                            if (!label && el.id) label = el.id;
                            if (!label) label = 'unlabeled';
                            const rawHref = el.getAttribute('href');
                            if (rawHref && rawHref.trim() !== '') {
                                href = rawHref.trim();
                            }
                        } else if (tagName === 'input' || tagName === 'textarea') {
                            // Priority: aria-label -> associated <label> -> placeholder -> name -> id -> unlabeled
                            const ariaLabel = (el.getAttribute('aria-label') || '').trim();
                            const assocLabel = getAssociatedLabelText(el);
                            const phAttr = (el.getAttribute('placeholder') || '').trim();
                            const nameAttr = (el.name || el.getAttribute('name') || '').trim();

                            if (ariaLabel) {
                                label = ariaLabel;
                            } else if (assocLabel) {
                                label = assocLabel;
                            } else if (nameAttr) {
                                label = nameAttr;
                            } else if (phAttr) {
                                label = phAttr;
                            } else if (el.id) {
                                label = el.id.trim();
                            } else {
                                label = 'unlabeled';
                            }

                            if (phAttr) {
                                placeholder = phAttr;
                            }

                            if (el.value !== undefined && el.value !== null && el.value.trim() !== '') {
                                value = el.value.trim();
                            }
                        } else if (tagName === 'button') {
                            label = (el.innerText || el.textContent || el.value || el.getAttribute('aria-label') || '').trim();
                            if (!label && el.id) label = el.id;
                            if (!label) label = 'unlabeled';
                        } else if (tagName === 'select') {
                            const ariaLabel = (el.getAttribute('aria-label') || '').trim();
                            const assocLabel = getAssociatedLabelText(el);
                            const nameAttr = (el.name || el.getAttribute('name') || '').trim();

                            if (ariaLabel) {
                                label = ariaLabel;
                            } else if (assocLabel) {
                                label = assocLabel;
                            } else if (nameAttr) {
                                label = nameAttr;
                            } else if (el.id) {
                                label = el.id.trim();
                            } else {
                                label = 'unlabeled';
                            }

                            const optList = Array.from(el.options).map(o => (o.text || o.textContent || '').trim()).filter(Boolean);
                            if (optList.length > 0) {
                                options = optList;
                            }

                            if (el.value !== undefined && el.value !== null && el.value.trim() !== '') {
                                value = el.value.trim();
                            }
                        }
                        
                        elements.push({
                            id: elementId,
                            type: elType,
                            label: label,
                            href: href || undefined,
                            placeholder: placeholder || undefined,
                            value: value || undefined,
                            options: options || undefined
                        });
                    }
                });
                
                const visibleText = document.body ? document.body.innerText.replace(/\\s+/g, ' ').trim().slice(0, 1500) : '';
                
                return {
                    url: window.location.href,
                    title: document.title,
                    visibleText: visibleText,
                    elements: elements
                };
            }
            """
            data = self.page.evaluate(js_script)
            
            # Format elements list as human/LLM readable text
            elem_lines = []
            for el in data["elements"]:
                line = f"[{el['id']}] {el['type']} \"{el['label']}\""
                if el.get("href"):
                    line += f" (href: {el['href']})"
                if el.get("placeholder"):
                    line += f" (placeholder: {el['placeholder']})"
                if el.get("options"):
                    opts_str = ", ".join(el["options"])
                    line += f" (options: {opts_str})"
                if el.get("value"):
                    line += f" (value: {el['value']})"
                elem_lines.append(line)

            elem_str = "\n".join(elem_lines) if elem_lines else "(No interactive elements found)"
            
            observation = (
                f"URL: {data['url']}\n"
                f"Title: {data['title']}\n\n"
                f"Page Text:\n{data['visibleText']}\n\n"
                f"Interactive Elements:\n{elem_str}"
            )
            return self._wrap_result(ok=True, observation=observation)
        except Exception as e:
            err = f"Failed to read page: {str(e)}"
            return self._wrap_result(ok=False, observation=err, error=err)

    def click(self, element_id: int) -> Dict[str, Any]:
        """
        Click an interactive element identified by its integer data-agent-id.
        """
        try:
            selector = f'[data-agent-id="{element_id}"]'
            locator = self.page.locator(selector)
            if locator.count() == 0:
                err = f"Element ID {element_id} not found on current page."
                return self._wrap_result(ok=False, observation=err, error=err)
            
            locator.click(timeout=5000)
            return self._wrap_result(
                ok=True,
                observation=f"Successfully clicked element [{element_id}]."
            )
        except PlaywrightTimeoutError:
            err = f"Clicking element [{element_id}] timed out after 5s."
            return self._wrap_result(ok=False, observation=err, error=err)
        except Exception as e:
            err = f"Click failed on element [{element_id}]: {str(e)}"
            return self._wrap_result(ok=False, observation=err, error=err)

    def type_text(self, element_id: int, text: str) -> Dict[str, Any]:
        """
        Type text into an input field identified by integer data-agent-id.
        Clears field first. If element is <input type="date">, requires YYYY-MM-DD ISO format.
        """
        try:
            selector = f'[data-agent-id="{element_id}"]'
            locator = self.page.locator(selector)
            if locator.count() == 0:
                err = f"Element ID {element_id} not found on current page."
                return self._wrap_result(ok=False, observation=err, error=err)
            
            # Check element input type
            input_type = (locator.get_attribute("type") or "").lower()
            if input_type == "date":
                # Validate ISO format YYYY-MM-DD
                if not re.match(r"^\d{4}-\d{2}-\d{2}$", text.strip()):
                    err = "Date must be in YYYY-MM-DD format."
                    return self._wrap_result(
                        ok=False,
                        observation=f"Invalid date format '{text}'. Date must be in YYYY-MM-DD format.",
                        error=err
                    )
                locator.fill(text.strip())
            else:
                locator.fill("")
                locator.fill(text)
            
            return self._wrap_result(
                ok=True,
                observation=f"Successfully typed '{text}' into element [{element_id}]."
            )
        except PlaywrightTimeoutError:
            err = f"Typing into element [{element_id}] timed out."
            return self._wrap_result(ok=False, observation=err, error=err)
        except Exception as e:
            err = f"Type text failed on element [{element_id}]: {str(e)}"
            return self._wrap_result(ok=False, observation=err, error=err)

    def screenshot(self, path: str = "screenshots/page.png") -> Dict[str, Any]:
        """Save a PNG screenshot of the current page into screenshots/ directory."""
        try:
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
            self.page.screenshot(path=path, full_page=True)
            return self._wrap_result(
                ok=True,
                observation=f"Screenshot saved to '{path}'."
            )
        except Exception as e:
            err = f"Failed to take screenshot: {str(e)}"
            return self._wrap_result(ok=False, observation=err, error=err)

    def close(self):
        """Cleanly close page, context, browser, and Playwright process."""
        try:
            self.page.close()
            self._context.close()
            self._browser.close()
            self._playwright.stop()
        except Exception:
            pass
