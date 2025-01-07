import { BufferMemory } from 'langchain/memory';
import { VectorStoreRetrieverMemory } from 'langchain/memory';
import { OpenAIEmbeddings } from 'langchain/embeddings/openai';
import { MemoryVectorStore } from 'langchain/vectorstores/memory';

interface TweetMemory {
  text: string;
  likes: number;
  retweets: number;
  replies: number;
  engagement_rate: number;
  timestamp: string;
}

export class TwitterMemoryManager {
  private conversationMemory: BufferMemory;
  private vectorMemory: VectorStoreRetrieverMemory;
  private tweetHistory: TweetMemory[] = [];

  constructor() {
    // Initialize conversation memory for short-term context
    this.conversationMemory = new BufferMemory({
      memoryKey: "chat_history",
      returnMessages: true,
    });

    // Initialize vector memory for long-term pattern recognition
    const vectorStore = new MemoryVectorStore(new OpenAIEmbeddings());
    this.vectorMemory = new VectorStoreRetrieverMemory({
      vectorStoreRetriever: vectorStore.asRetriever(4),
      memoryKey: "relevant_history",
    });
  }

  async addTweet(tweet: TweetMemory): Promise<void> {
    this.tweetHistory.push(tweet);
    
    // Store in vector memory for similarity search
    const tweetContent = JSON.stringify(tweet);
    await this.vectorMemory.saveContext(
      { input: "Tweet Performance" },
      { output: tweetContent }
    );
  }

  async getMostSuccessfulPatterns(): Promise<string> {
    // Sort tweets by engagement rate
    const sortedTweets = [...this.tweetHistory].sort(
      (a, b) => b.engagement_rate - a.engagement_rate
    );

    // Get top performing tweets
    const topTweets = sortedTweets.slice(0, 5);
    
    return JSON.stringify(topTweets, null, 2);
  }

  async getSimilarSuccessfulTweets(content: string): Promise<TweetMemory[]> {
    const result = await this.vectorMemory.loadMemoryVariables({ input: content });
    return result.relevant_history;
  }

  async getMemoryVariables(): Promise<{ [key: string]: any }> {
    const conversationHistory = await this.conversationMemory.loadMemoryVariables({});
    const vectorHistory = await this.vectorMemory.loadMemoryVariables({});
    
    return {
      ...conversationHistory,
      ...vectorHistory,
      successful_patterns: await this.getMostSuccessfulPatterns(),
    };
  }

  calculateEngagementRate(tweet: Partial<TweetMemory>): number {
    const { likes = 0, retweets = 0, replies = 0 } = tweet;
    return (likes + retweets * 2 + replies * 3) / 100;
  }

  async getEngagementInsights(): Promise<string> {
    if (this.tweetHistory.length === 0) {
      return "No tweet history available yet.";
    }

    const totalTweets = this.tweetHistory.length;
    const avgEngagement = this.tweetHistory.reduce(
      (sum, tweet) => sum + tweet.engagement_rate, 
      0
    ) / totalTweets;

    const timeAnalysis = this.analyzePostingTimes();
    const contentAnalysis = this.analyzeContentPatterns();

    return JSON.stringify({
      total_tweets: totalTweets,
      average_engagement: avgEngagement,
      best_posting_times: timeAnalysis,
      successful_content_patterns: contentAnalysis
    }, null, 2);
  }

  private analyzePostingTimes(): { [key: string]: number } {
    const engagementByHour: { [hour: string]: { total: number; count: number } } = {};
    
    this.tweetHistory.forEach(tweet => {
      const hour = new Date(tweet.timestamp).getHours();
      if (!engagementByHour[hour]) {
        engagementByHour[hour] = { total: 0, count: 0 };
      }
      engagementByHour[hour].total += tweet.engagement_rate;
      engagementByHour[hour].count += 1;
    });

    // Calculate average engagement for each hour
    const hourlyAverages: { [hour: string]: number } = {};
    Object.entries(engagementByHour).forEach(([hour, data]) => {
      hourlyAverages[hour] = data.total / data.count;
    });

    return hourlyAverages;
  }

  private analyzeContentPatterns(): any {
    // Analyze common patterns in successful tweets
    const successfulTweets = this.tweetHistory
      .filter(tweet => tweet.engagement_rate > 0.5)
      .map(tweet => tweet.text);

    return {
      sample_size: successfulTweets.length,
      examples: successfulTweets.slice(0, 3)
    };
  }
}
