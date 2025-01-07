declare module 'agent-twitter-client' {
    export class Scraper {
        constructor();
        login(username: string, password: string, email?: string): Promise<void>;
        me(): Promise<any>;
        getLikedTweets(username: string, count?: number): Promise<any[]>;
        getTweet(id: string): Promise<any>;
        sendTweet(text: string, replyTo?: string, media?: any[]): Promise<void>;
    }
}
