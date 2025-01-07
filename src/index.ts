import { config } from 'dotenv';
import { Scraper } from 'agent-twitter-client';
import OpenAI from 'openai';
import schedule from 'node-schedule';
import { ChatOpenAI } from 'langchain/chat_models/openai';
import { PromptTemplate } from 'langchain/prompts';
import { LLMChain } from 'langchain/chains';
import { 
  SystemMessagePromptTemplate,
  HumanMessagePromptTemplate,
  ChatPromptTemplate
} from 'langchain/prompts';
import { TwitterMemoryManager } from './memory';

// Load environment variables
config();

interface TweetAnalysis {
  topics: string[];
  sentiment: string;
  style: string;
  hashtags: string[];
  engagement_factors: string[];
}

class TwitterAgent {
  private scraper: Scraper;
  private openai: OpenAI;
  private model: ChatOpenAI;
  private analysisChain: LLMChain;
  private tweetGenerationChain: LLMChain;
  private memory: TwitterMemoryManager;

  constructor() {
    this.scraper = new Scraper();
    this.openai = new OpenAI({
      apiKey: process.env.OPENAI_API_KEY,
    });
    
    this.memory = new TwitterMemoryManager();
    
    // Initialize LangChain
    this.model = new ChatOpenAI({
      openAIApiKey: process.env.OPENAI_API_KEY,
      modelName: 'gpt-3.5-turbo',
      temperature: 0.7
    });

    // Create analysis chain
    const analysisPrompt = ChatPromptTemplate.fromPromptMessages([
      SystemMessagePromptTemplate.fromTemplate(
        "You are an expert social media analyst. Analyze the following tweets and provide detailed insights about:" +
        "\n1. Main topics and themes" +
        "\n2. Sentiment and emotional tone" +
        "\n3. Writing style and voice" +
        "\n4. Popular hashtags" +
        "\n5. Factors contributing to engagement" +
        "\nConsider these successful patterns from previous tweets: {successful_patterns}" +
        "\nProvide the analysis in a structured format."
      ),
      HumanMessagePromptTemplate.fromTemplate("{tweets}")
    ]);

    this.analysisChain = new LLMChain({
      llm: this.model,
      prompt: analysisPrompt,
      outputKey: "analysis"
    });

    // Create tweet generation chain
    const tweetPrompt = ChatPromptTemplate.fromPromptMessages([
      SystemMessagePromptTemplate.fromTemplate(
        "You are a creative social media expert. Based on the following content analysis and historical performance data, generate an engaging tweet that:" +
        "\n1. Matches the identified successful style" +
        "\n2. Uses relevant hashtags" +
        "\n3. Maintains similar tone and voice" +
        "\n4. Optimizes for engagement" +
        "\n5. Incorporates patterns from successful tweets: {successful_patterns}" +
        "\nKeep the tweet under 280 characters."
      ),
      HumanMessagePromptTemplate.fromTemplate("{analysis}")
    ]);

    this.tweetGenerationChain = new LLMChain({
      llm: this.model,
      prompt: tweetPrompt,
      outputKey: "tweet"
    });
  }

  async initialize() {
    try {
      await this.scraper.login(
        process.env.TWITTER_USERNAME!,
        process.env.TWITTER_PASSWORD!,
        process.env.TWITTER_EMAIL
      );
      console.log('Successfully logged into Twitter');
    } catch (error) {
      console.error('Failed to login to Twitter:', error);
      throw error;
    }
  }

  async fetchLikedTweets(count: number = 10): Promise<string[]> {
    try {
      const tweets = await this.scraper.getLikedTweets(process.env.TWITTER_USERNAME!, count);
      return tweets.map(tweet => tweet.text);
    } catch (error) {
      console.error('Error fetching liked tweets:', error);
      return [];
    }
  }

  async analyzeTweets(tweets: string[]): Promise<string | null> {
    try {
      const tweetsText = tweets.join('\n');
      const memoryVars = await this.memory.getMemoryVariables();
      
      const response = await this.analysisChain.call({
        tweets: tweetsText,
        ...memoryVars
      });

      return response.analysis;
    } catch (error) {
      console.error('Error analyzing tweets:', error);
      return null;
    }
  }

  async generateTweet(analysis: string): Promise<string | null> {
    try {
      const memoryVars = await this.memory.getMemoryVariables();
      
      const response = await this.tweetGenerationChain.call({
        analysis: analysis,
        ...memoryVars
      });

      return response.tweet;
    } catch (error) {
      console.error('Error generating tweet:', error);
      return null;
    }
  }

  async postTweet(tweetText: string): Promise<void> {
    try {
      await this.scraper.sendTweet(tweetText);
      console.log('Successfully posted tweet:', tweetText);
      
      // Track the tweet in memory
      const tweet = {
        text: tweetText,
        likes: 0,
        retweets: 0,
        replies: 0,
        engagement_rate: 0,
        timestamp: new Date().toISOString()
      };
      
      await this.memory.addTweet(tweet);
      
      // Schedule engagement check
      setTimeout(async () => {
        await this.updateTweetEngagement(tweet);
      }, 24 * 60 * 60 * 1000); // Check after 24 hours
      
    } catch (error) {
      console.error('Error posting tweet:', error);
    }
  }

  private async updateTweetEngagement(tweet: any): Promise<void> {
    try {
      // Get updated tweet stats
      const updatedTweet = await this.scraper.getTweet(tweet.id);
      
      const engagementData = {
        text: tweet.text,
        likes: updatedTweet.likes,
        retweets: updatedTweet.retweets,
        replies: updatedTweet.replies,
        engagement_rate: this.memory.calculateEngagementRate(updatedTweet),
        timestamp: tweet.timestamp
      };
      
      await this.memory.addTweet(engagementData);
      
      // Log engagement insights
      const insights = await this.memory.getEngagementInsights();
      console.log('Updated Engagement Insights:', insights);
      
    } catch (error) {
      console.error('Error updating tweet engagement:', error);
    }
  }

  async runCycle(): Promise<void> {
    console.log('Starting tweet cycle...');
    const likedTweets = await this.fetchLikedTweets();
    
    if (likedTweets.length > 0) {
      const analysis = await this.analyzeTweets(likedTweets);
      
      if (analysis) {
        const newTweet = await this.generateTweet(analysis);
        
        if (newTweet) {
          await this.postTweet(newTweet);
          
          // Log current insights
          const insights = await this.memory.getEngagementInsights();
          console.log('Current Performance Insights:', insights);
        }
      }
    }
  }
}

async function main() {
  const agent = new TwitterAgent();
  
  try {
    // Initialize and login
    await agent.initialize();

    // Run initial cycle
    await agent.runCycle();

    // Schedule tweets every 6 hours
    schedule.scheduleJob('0 */6 * * *', async () => {
      await agent.runCycle();
    });

    console.log('Agent is running and will post tweets every 6 hours');
  } catch (error) {
    console.error('Failed to start the agent:', error);
    process.exit(1);
  }
}

main().catch(console.error);
