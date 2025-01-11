import logging
from playwright.async_api import async_playwright
import os
import time
from typing import Optional
import asyncio

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TwitterBrowser:
    def __init__(self):
        """Initialize TwitterBrowser"""
        self.browser = None
        self.context = None
        self.page = None
        self._playwright = None
        
    async def start(self):
        """Start the browser and create a new context"""
        try:
            # Initialize playwright first
            self._playwright = await async_playwright().start()
            if not self._playwright:
                raise Exception("Failed to initialize playwright")
            
            # Get browser arguments from environment
            browser_args = os.getenv('BROWSER_ARGS', '').split()
            
            # Add additional arguments for stability and memory management
            default_args = [
                '--disable-dev-shm-usage',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-accelerated-2d-canvas',
                '--disable-gpu',
                '--disable-notifications',
                '--disable-background-timer-throttling',
                '--disable-backgrounding-occluded-windows',
                '--disable-breakpad',
                '--disable-component-extensions-with-background-pages',
                '--disable-extensions',
                '--disable-features=TranslateUI,BlinkGenPropertyTrees',
                '--disable-ipc-flooding-protection',
                '--disable-renderer-backgrounding',
                '--enable-features=NetworkService,NetworkServiceInProcess',
                '--force-color-profile=srgb',
                '--hide-scrollbars',
                '--metrics-recording-only',
                '--mute-audio',
                # Memory management
                '--js-flags="--max-old-space-size=256"',
                '--memory-pressure-off',
                '--single-process',
                '--aggressive-cache-discard',
                '--disable-cache',
                '--disable-application-cache',
                '--disable-offline-load-stale-cache',
                '--disk-cache-size=0',
            ]
            
            browser_args.extend(default_args)
            
            # Launch browser with combined arguments and increased timeouts
            self.browser = await self._playwright.chromium.launch(
                args=browser_args,
                headless=True if os.getenv('RAILWAY_ENVIRONMENT') == 'production' else False,
                timeout=60000,
            )
            
            if not self.browser:
                raise Exception("Failed to launch browser")
            
            # Create context with optimized memory settings
            self.context = await self.browser.new_context(
                viewport={'width': 800, 'height': 600},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
                ignore_https_errors=True,
                java_script_enabled=True,
                bypass_csp=True,
                extra_http_headers={'Accept-Language': 'en-US,en;q=0.9'},
                storage_state=None,
                proxy=None,
            )
            
            if not self.context:
                raise Exception("Failed to create browser context")
            
            # Create new page with increased timeouts
            self.page = await self.context.new_page()
            if not self.page:
                raise Exception("Failed to create new page")
                
            await self.page.set_default_timeout(30000)
            await self.page.set_default_navigation_timeout(30000)
            
            # Add error handling
            self.page.on('crash', lambda: logger.error('Page crashed'))
            self.page.on('pageerror', lambda err: logger.error(f'Page error: {err}'))
            
            # Configure request interception to block unnecessary resources
            await self.page.route('**/*.{png,jpg,jpeg,gif,svg,css,woff,woff2,ttf}', lambda route: route.abort())
            await self.page.route('**/*', lambda route: route.continue_())
            
            # Add periodic garbage collection
            async def gc_task():
                while True:
                    await asyncio.sleep(30)
                    try:
                        if self.page and not self.page.is_closed():
                            await self.page.evaluate('() => { gc(); }')
                    except Exception as e:
                        logger.warning(f"GC failed: {str(e)}")
            
            asyncio.create_task(gc_task())
            
            logger.info("Browser started successfully")
            return self.page
            
        except Exception as e:
            logger.error(f"Error starting browser: {str(e)}")
            await self.close()
            raise
            
    async def close(self):
        """Close all browser resources"""
        try:
            if self.page and not self.page.is_closed():
                await self.page.close()
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self._playwright:
                await self._playwright.stop()
        except Exception as e:
            logger.error(f"Error closing browser: {str(e)}")
            
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
