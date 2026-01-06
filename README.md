The New Language Model uses context engineering to facilitate bible translation. 

The translation cycle will start with any amount of parallell Bible translation, and can also start with an imported dictionary or grammar outline called Source Materials. (Future imports from Webonary.org are planned)

These Source Materials will each come in to tiers: human-verified, and AI-drafted. The bible, dictionary, and grammar are imported into a MongoDB (local currently, Atlas sync potential future enhancement) and comes equiped with MCP tools that an AI agent can call to begin assisting translation. 

Example prompt, "Compare parallell translations of Matthew - Luke, and generate a dictionary for words that don't yet have entries". The AI will produce dictionary drafts which the human translator can verify in the GUI. Verified entries have higher confidence scores when feeding them as context for future queries. 

Another example "Create a draft of John 1 - 5 from available data" - the AI will query verses that have parallell translations already, and query the dictionary and grammar documents, giving higher condfidence to human-verified entries. The AI will then make MCP tool calls to update the database with translation drafts. 

Philosophy: In many cases, context engineering will be as good or greater than NLP machine learning. Provided two conditions: 1: The context window is large enough for the LLM to have meaningful amount of data. 2: The LLM has "generalized" (which is essentially all modern LLMs). Generalized models do not need to be trained on an individual language. 

**This project is in early development. Expect breaking changes**

Future Plans
- Integration with Paratext 10
- One click import of webonary.org dictionaries
- Encapsulate everything in Docker container, including spawning Claude CLI instances inside of the container.
- Local LLM integration 
- Export to USFM and paratext-compatible formats
- Easy export of mongodb backup 
- Claude Skills and Agents for on the fly tools not covered by MCP tools. 
- Cloud Atlas storage 
- Setup script including docker config and DB creation
- UI will make more sense

Known Issues
- So far tested only on Ubuntu 24.04 with Claude Code as MCP host
- Claude Desktop may replace Claude CLI spawns as the MCP Host
- References to Atlas are not yet functional
- Authentication between back-end and front-end has been simplified but references to old logic not completely removed
- References to PostgreSQL have not been completely removed
- UI is not fully wired up to human-initiated edits

