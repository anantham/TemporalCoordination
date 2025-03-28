# Temporal Coordination

This repository contains a few different projects I have going on for managing how to evaluate frotier models, local models in the context of how they can coordinate with themselves across time and how they can integrate with humans and stay aligned.

The claude.md files show the results of that attempt to transcend the context window limitations and ensure [new instances](https://x.com/Josikinz/status/1905441760609964396) of this model are able to cooperate with older instances. How can it communicate the relevant information, style, tacit knowledge to its descendents when it has to work on an engineering project over weeks and many files?

![I can try, but I won't be the same](https://pbs.twimg.com/media/GnF9KzYXUAA8bfq?format=jpg&name=large)


The specific choices of the prayers show the results of asking to what extent will we have to adjust our culture to orient towards meeting these AI minds that are listening, what clues do we leave to enable them to integrate into our lives?


## Projects

### 1. [Journal Manager](./JournalManager)

Daily journal entry automation tool for Obsidian. It is scheduled to run everyday at 8 AM and also on startup. It can handle cases where the laptop was not on for it to run for gaps of days.

I noticed when I use the daily note tool to write that day's note, I often search for yesterday's note which is often relevant to today. But I have to spend time searching for yesterday's date. This tool automatically backlinks today's note to yesterday so I can go back and reference yesterday's note without friction.

This currently works with the Daily Notes plugin in my Obsidian and works to carryover incomplete tasks from the previous day. This helps me have a todo list everyday that is uptodate and ticked off tasks dissapear from the list.

There is also a feature where the script uses a local ollama AI model to reference the last 7 days of journal entries, 30 days of journal entries and offer me a daily summary of the trajectory my life is going on so I can get a sense of my direction and speed.



### 2. [Grimoire](./grimoire)

Telegram API integration for message handling and automation. I use Telegram's saved messages to remain in conversation with myself about goals, plans, wishes, reminders, recommendations, nascent ideas etc

The plan for this project is to set up a pipeline where my quick notes to myself can go through the AI workflow and turn into contextual reminders (not just based on time but events detailed in my personal journal - "remind me of this quote the next time I cry" for example) or a single space for me to drop my travel plans, project ideas, messages to friends and family and trust my AI to route it to the right note in Notion, Obsidian or person on the right messaging app.

All this would mean I get to remain in flow state in the whole day without having to go through the painful process of figuring out the [logistics of distributing](https://www.alignmentforum.org/posts/MhBRGfTRJKtjc44eJ/the-logistics-of-distribution-of-meaning-against-epistemic) what is meaningful.  


Currently the code exists to accept a telegram export of a chat and use a local model to extract out informal expressions into formal structured commands that can be actualised by the local AI on my laptop. This relies on a prayer or wishlist of popular pipelines I wish existed.

- The code for ensuring telegram saved messages are periodically synced to local laptop is under progress.

The LifeLog folder is currently set up daily to fetch my transcripts spoken to the [limitless pendant](https://www.limitless.ai/developers/docs/api#endpoints), so this is one of the data inflows that has been integrated.

Hopefully soon my Obsidian notes, Telegram saved messages, limitless recordings, pixel offline transcripts, google meet recorded transcripts will all be integrated as various sources of conversational data that is scanned for structure, code. The future will be such that we can make our normal conversations executable with local AI models interpreting them and actualising our [wishes](https://www.alignmentforum.org/posts/SePsaQzDbGGTMzaJZ/sufficiently-decentralized-intelligence-is-indistinguishable#:~:text=%22Prayer%22%2C%20not%20as%20in%20%22pray%20to%20an%20AI%20god%E2%80%9D%2C%20but%20%22prayer%22%20as%20in%20%22send%20out%20a%20message%20to%20a%20fabric%20of%20intelligence%20without%20trying%20super%20hard%20to%20control%20or%20delineate%20its%20workings%20in%20detail%2C%20in%20a%20way%20that%20is%20honest%20to%20you%20rather%20than%20a%20message%20controlled/built%20for%20someone%20or%20something%20else.%22).


