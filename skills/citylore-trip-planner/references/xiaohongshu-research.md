# Xiaohongshu Research Flow

## MCP tools to use

- `search_feeds`
- `get_feed_detail`

## Search query pattern

For a destination city, run multiple searches instead of one broad query:

- `城市名 攻略`
- `城市名 本地人推荐`
- `城市名 美食`
- `城市名 咖啡`
- `城市名 夜市`
- `城市名 博物馆`
- `城市名 市集`
- `城市名 探店`
- `城市名 工作室`
- `城市名 街区`

For Jingdezhen-like destinations, add craft-specific terms:

- `景德镇 陶艺`
- `景德镇 瓷器`
- `景德镇 陶溪川`
- `景德镇 三宝村`

## Candidate extraction format

Normalized batch files should contain a top-level `candidates` array. Each candidate should look like:

```json
{
  "place_name": "陶溪川文创街区",
  "city": "景德镇",
  "district": "珠山区",
  "address": "可选",
  "category": "attraction",
  "tags": ["pottery", "night-walk", "market"],
  "why_go": "夜游和逛店密度高，适合第一晚。",
  "body": "来自多篇小红书攻略的高频推荐，适合傍晚和夜间安排。",
  "source_feed_id": "feed_id_here",
  "source_title": "笔记标题",
  "source_author": "作者昵称",
  "priority": 0.92
}
```

## Promotion rule

- Keep all extracted material in `imports/xiaohongshu/`
- Promote only the best city-relevant candidates into canonical places
- Prefer stable POIs, neighborhoods, markets, museums, parks, and food landmarks
- When the user wants less touristy plans, over-sample queries that imply local repeat behavior, night walks, local food, side-street coffee, or maker spaces
