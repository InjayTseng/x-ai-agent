import * as dotenv from 'dotenv';
import { Scraper } from '../temp-twitter-client/dist/node/esm/index.mjs';

// Define our own Tweet interface since the library's one is not exported
interface Author {
    username: string;
    name: string;
    id: string;
}

interface Tweet {
    id: string;
    text: string;
    author: Author;
    likes: number;
    retweets: number;
    createdAt: Date;
    isLiked?: boolean;
}

// Twitter API v2 response types
interface TwitterV2User {
    id: string;
    name: string;
    username: string;
}

interface TwitterV2Tweet {
    id: string;
    text: string;
    author_id: string;
    created_at: string;
    public_metrics?: {
        like_count: number;
        retweet_count: number;
    };
}

interface TwitterV2Response {
    data: TwitterV2Tweet[];
    includes?: {
        users?: TwitterV2User[];
    };
}

dotenv.config();

class LikeMonitor {
    private scraper: Scraper;
    private lastCheckedTweets: Set<string> = new Set();
    private isRunning = false;
    private userId: string | null = null;

    constructor() {
        this.scraper = new Scraper();
    }

    async initialize() {
        if (!process.env.TWITTER_USERNAME || !process.env.TWITTER_PASSWORD) {
            throw new Error('Twitter credentials not found in environment variables');
        }

        console.log('Initializing Twitter like monitor...');
        await this.scraper.login(
            process.env.TWITTER_USERNAME,
            process.env.TWITTER_PASSWORD,
            process.env.TWITTER_EMAIL || undefined,
            undefined, // twoFactorSecret
            undefined, // appKey
            undefined, // appSecret
            undefined, // accessToken
            undefined  // accessSecret
        );
        console.log('Login successful!');

        // Get our user ID
        const profile = await this.scraper.me();
        if (!profile) {
            throw new Error('Could not get user profile');
        }
        this.userId = profile.userId;
        console.log('Got user ID:', this.userId);
    }

    private async getLikedTweets(): Promise<Tweet[]> {
        if (!this.userId) {
            throw new Error('User ID not initialized');
        }

        console.log('Fetching liked tweets...');
        const tweets: Tweet[] = [];
        try {
            // Make a direct request to get liked tweets using v2 API
            const response = await fetch(`https://api.twitter.com/2/users/${this.userId}/liked_tweets?tweet.fields=public_metrics,created_at&expansions=author_id&user.fields=name,username`, {
                headers: {
                    'Authorization': `Bearer ${this.scraper.token}`,
                    'Cookie': (await this.scraper.getCookies()).map(c => `${c.key}=${c.value}`).join('; ')
                }
            });

            if (!response.ok) {
                console.error('Failed to fetch liked tweets:', response.status, response.statusText);
                const text = await response.text();
                console.error('Response:', text);
                return tweets;
            }

            const data = await response.json() as TwitterV2Response;
            console.log('Liked tweets response:', JSON.stringify(data, null, 2));

            // Parse the response and add tweets
            if (data.data && Array.isArray(data.data)) {
                const users = new Map(data.includes?.users?.map(user => [user.id, user]) || []);
                
                for (const tweet of data.data) {
                    const user = users.get(tweet.author_id);
                    if (!user) continue;

                    tweets.push({
                        id: tweet.id,
                        text: tweet.text || '',
                        author: {
                            username: user.username,
                            name: user.name,
                            id: user.id
                        },
                        likes: tweet.public_metrics?.like_count || 0,
                        retweets: tweet.public_metrics?.retweet_count || 0,
                        createdAt: new Date(tweet.created_at),
                        isLiked: true
                    });
                }
            }
            
            console.log(`Found total of ${tweets.length} liked tweets`);
            return tweets;
        } catch (error) {
            console.error('Error fetching liked tweets:', error);
            throw error;
        }
    }

    private processTweet(tweet: Tweet) {
        console.log('\n🔍 New Liked Tweet Detected:');
        console.log('------------------------');
        console.log(`Author: @${tweet.author.username} (${tweet.author.name})`);
        console.log(`Content: ${tweet.text}`);
        console.log(`Likes: ${tweet.likes}`);
        console.log(`Retweets: ${tweet.retweets}`);
        console.log(`URL: https://twitter.com/${tweet.author.username}/status/${tweet.id}`);
        console.log('------------------------');
    }

    async startMonitoring(intervalSeconds: number = 60) {
        if (this.isRunning) {
            console.log('Monitor is already running!');
            return;
        }

        this.isRunning = true;
        console.log(`Starting to monitor liked tweets every ${intervalSeconds} seconds...`);

        // Initial fetch to set baseline
        const initialTweets = await this.getLikedTweets();
        initialTweets.forEach(tweet => this.lastCheckedTweets.add(tweet.id));

        while (this.isRunning) {
            try {
                console.log('\n⏳ Checking for new liked tweets...');
                const currentTweets = await this.getLikedTweets();
                
                // Check for new tweets that weren't in our last check
                for (const tweet of currentTweets) {
                    if (!this.lastCheckedTweets.has(tweet.id)) {
                        this.processTweet(tweet);
                        this.lastCheckedTweets.add(tweet.id);
                    }
                }

                // Keep set size manageable
                if (this.lastCheckedTweets.size > 1000) {
                    const oldestTweets = Array.from(this.lastCheckedTweets).slice(0, 500);
                    oldestTweets.forEach(id => this.lastCheckedTweets.delete(id));
                }

                await new Promise(resolve => setTimeout(resolve, intervalSeconds * 1000));
            } catch (error) {
                console.error('Error while monitoring tweets:', error);
                await new Promise(resolve => setTimeout(resolve, 5000)); // Wait 5 seconds before retrying
            }
        }
    }

    stop() {
        this.isRunning = false;
        console.log('Stopping tweet monitor...');
    }
}

// Start monitoring
console.log('Starting the monitor...');
const monitor = new LikeMonitor();

// Handle graceful shutdown
process.on('SIGINT', () => {
    console.log('\nReceived SIGINT. Shutting down...');
    monitor.stop();
});

console.log('Initializing monitor...');
monitor.initialize()
    .then(() => {
        console.log('Monitor initialized successfully');
        return monitor.startMonitoring(10); // Check every 10 seconds
    })
    .catch(error => {
        console.error('Failed to start monitoring:', error);
        process.exit(1);
    });
