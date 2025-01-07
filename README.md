# AI-Powered Twitter Agent

This project implements an AI-powered Twitter agent that can monitor and interact with Twitter using automated processes. The agent is built using TypeScript and integrates with the `agent-twitter-client` library for Twitter interactions.

## Features

### 1. Twitter Authentication
- Secure login using username, password, and email
- Support for OAuth authentication
- Robust error handling and logging during authentication

### 2. Like Monitoring
- Real-time monitoring of liked tweets
- Automatic detection of new likes
- Detailed logging of liked tweet information including:
  - Tweet content
  - Author information
  - Engagement metrics (likes, retweets)
  - Tweet URLs

## Project Structure

- `src/`
  - `like-monitor.ts`: Implements the tweet like monitoring functionality
  - `test-login.ts`: Test script for Twitter authentication
  - `memory.ts`: Handles agent memory and state management
  - `index.ts`: Main entry point for the Twitter agent
  - `types/`: TypeScript type definitions

## Setup

1. Clone the repository
2. Install dependencies:
   ```bash
   npm install
   ```
3. Create a `.env` file with the following variables:
   ```
   TWITTER_USERNAME=your_username
   TWITTER_PASSWORD=your_password
   TWITTER_EMAIL=your_email
   OPENAI_API_KEY=your_openai_key
   ```

## Usage

### Running the Like Monitor
```bash
node --loader ts-node/esm src/like-monitor.ts
```

This will start monitoring your liked tweets and display information about newly liked tweets in real-time.

## Dependencies

- `agent-twitter-client`: Custom Twitter client library
- `dotenv`: Environment variable management
- `ts-node`: TypeScript execution environment
- `typescript`: TypeScript support
- `langchain`: AI/ML capabilities
- `node-schedule`: Task scheduling
- `openai`: OpenAI API integration

## Error Handling

The project includes comprehensive error handling for:
- Authentication failures
- API rate limits
- Network issues
- Invalid responses

## Future Enhancements

- Sentiment analysis of liked tweets
- Automated engagement based on content
- Enhanced monitoring capabilities
- Integration with more Twitter features

## Contributing

Feel free to submit issues and enhancement requests!

## License

This project is licensed under the MIT License - see the LICENSE file for details.
