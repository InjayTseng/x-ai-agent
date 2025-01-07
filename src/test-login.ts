import * as dotenv from 'dotenv';
import { Scraper } from '../temp-twitter-client/dist/node/esm/index.mjs';

// Load environment variables
dotenv.config();

async function testTwitterLogin() {
    console.log('Starting Twitter login test...');
    console.log(`Attempting to login with username: ${process.env.TWITTER_USERNAME}`);
    
    const scraper = new Scraper();
    
    try {
        console.log('Initializing Twitter scraper...');
        
        console.log('Attempting login...');
        await scraper.login(
            process.env.TWITTER_USERNAME!,
            process.env.TWITTER_PASSWORD!,
            process.env.TWITTER_EMAIL,
            undefined, // twoFactorSecret
            undefined, // appKey
            undefined, // appSecret
            undefined, // accessToken
            undefined  // accessSecret
        );
        
        console.log('Login successful! Verifying connection...');
        
        // Test if we can fetch the user's profile
        console.log('Attempting to fetch user profile...');
        const profile = await scraper.me();
        console.log('Successfully retrieved profile:', profile);
        
        console.log('\nAll tests passed successfully! Twitter connection is working.');
    } catch (error) {
        console.error('\n❌ Error during Twitter login test:', error);
        console.error('Full error details:', JSON.stringify(error, null, 2));
        throw error;
    } finally {
        console.log('\nTest completed.');
    }
}

// Run the test
testTwitterLogin().catch(error => {
    console.error('Test failed:', error);
    process.exit(1);
});
