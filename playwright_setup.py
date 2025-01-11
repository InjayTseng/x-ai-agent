import logging
from playwright.async_api import async_playwright
import os
import time
from typing import Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TwitterBrowser:
    def __init__(self):
        self.browser = None
        self.context = None
        self.page = None
        
    async def start(self, headless: bool = True) -> bool:
        """Start the browser"""
        try:
            # Force headless mode in production environment
            is_production = os.environ.get('RAILWAY_ENVIRONMENT') == 'production'
            headless = True if is_production else headless
            
            # Get browser arguments from environment or use defaults
            browser_args = os.environ.get('BROWSER_ARGS', '').split() or [
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu'
            ]
            
            playwright = await async_playwright().start()
            self.browser = await playwright.chromium.launch(
                headless=headless,
                args=browser_args
            )
            self.context = await self.browser.new_context(
                viewport={'width': 1280, 'height': 720},
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                ignore_https_errors=True,  # 添加此項以處理可能的 SSL 問題
                bypass_csp=True  # 添加此項以繞過內容安全策略
            )
            
            # 設置更長的超時時間
            self.context.set_default_timeout(30000)  # 30 秒
            self.context.set_default_navigation_timeout(30000)
            
            self.page = await self.context.new_page()
            
            # Add stealth scripts
            await self._add_stealth_scripts()
            logger.info("Browser started successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to start browser: {str(e)}")
            return False
            
    async def login(self, email: str, password: str, account_name: str) -> bool:
        """Login to Twitter"""
        try:
            if not self.page:
                raise Exception("Browser not started")
                
            logger.info("Navigating to Twitter login page...")
            await self.page.goto("https://twitter.com/i/flow/login")
            await self.page.wait_for_timeout(3000)  # Wait for page to stabilize
            
            # Enter email
            logger.info("Entering email...")
            await self.page.wait_for_selector('input[autocomplete="username"]', timeout=10000)
            email_input = await self.page.query_selector('input[autocomplete="username"]')
            await email_input.fill(email)
            await self.page.wait_for_timeout(1000)
            
            # Click Next
            next_button = await self.page.query_selector('div[role="button"]:has-text("Next")')
            if next_button:
                await next_button.click()
                logger.info("Successfully clicked Next button")
            else:
                await self.page.keyboard.press('Enter')
            
            await self.page.wait_for_timeout(2000)
            
            # Handle username verification if needed
            try:
                username_input = await self.page.query_selector('input[data-testid="ocfEnterTextTextInput"]')
                if username_input:
                    logger.info("Username verification required...")
                    await username_input.fill(account_name)
                    await self.page.wait_for_timeout(1000)
                    
                    next_after_username = await self.page.query_selector('div[role="button"]:has-text("Next")')
                    if next_after_username:
                        await next_after_username.click()
                    else:
                        await self.page.keyboard.press('Enter')
                        
                    await self.page.wait_for_timeout(2000)
            except Exception as e:
                logger.debug(f"No username verification needed: {str(e)}")
            
            # Enter password
            logger.info("Entering password...")
            password_input = await self.page.wait_for_selector('input[name="password"]', timeout=10000)
            await password_input.fill(password)
            await self.page.wait_for_timeout(1000)
            
            # Click Login
            login_button = await self.page.query_selector('div[role="button"]:has-text("Log in")')
            if login_button:
                await login_button.click()
                logger.info("Successfully clicked Login button")
            else:
                await self.page.keyboard.press('Enter')
            
            await self.page.wait_for_timeout(5000)
            
            # Verify successful login
            try:
                await self.page.wait_for_selector('[data-testid="AppTabBar_Home_Link"]', timeout=10000)
                logger.info("Successfully logged in to Twitter")
                return True
            except Exception:
                logger.error("Login verification failed")
                # Take screenshot for debugging
                await self.page.screenshot(path='login_error.png')
                return False
                
        except Exception as e:
            logger.error(f"Login failed with exception: {str(e)}")
            # Take screenshot for debugging
            await self.page.screenshot(path='login_error_exception.png')
            return False
            
    def get_page(self):
        """Get the current page"""
        return self.page
        
    async def close(self):
        """Close the browser"""
        try:
            if self.page:
                await self.page.close()
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            logger.info("Browser resources closed successfully")
        except Exception as e:
            logger.error(f"Error closing browser: {str(e)}")
            
    async def _add_stealth_scripts(self):
        """Add scripts to help avoid detection"""
        await self.page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        });
        """)
        
    async def is_logged_in(self) -> bool:
        """Check if currently logged in to Twitter"""
        try:
            return await self.page.locator('[data-testid="primaryColumn"]').is_visible(timeout=1000)
        except:
            return False
