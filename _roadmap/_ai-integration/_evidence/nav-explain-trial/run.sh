#!/bin/sh
# Run from app/. cards.json built with: node scripts/build-cards.mjs --data public/data --limit 40 --out <scratch>
node scripts/assistant-cli.mjs --data public/data --cards $1 --protocol openai \
  --endpoint http://127.0.0.1:11434/v1/chat/completions --model gpt-oss:20b-f1 \
  --file ../_roadmap/_ai-integration/_evidence/nav-explain-trial/questions.json --out ../_roadmap/_ai-integration/_evidence/nav-explain-trial/raw-run.json --text-out ../_roadmap/_ai-integration/_evidence/nav-explain-trial/raw-run.txt
