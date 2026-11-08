# Chat-phrase weights (IME-545)

## Problem

Wanxiang's weights come from written text, which under-counts the short replies of a
chat. 是的 has 2,727 against 四个's 42,848 and 是否's 213,074, 在吗 has 0, 对的 386.
On nine-key, where many words share one digit string, such a phrase loses to a
written-language word with the same digits: 74433 offers 十分 before 是的, 92462
offers 在哪 and 在那 before 在吗, and with the last syllable cut short (7443, the
case users reported) 是的 is not on the first three pages at all. Nine-key tail
completion (see [recipe corrections](recipe-corrections.md)) makes the phrases
reachable; their weight decides whether they come first.

## Mechanism

`weights` in `tools/local_additions.json` lists exact upstream rows: the text, its
reading exactly as the upstream table writes it (with tone marks), the weight to
raise it to, the upstream weight it was reviewed against, and the reason.
`local_additions.apply` runs on every build after the upstream tables are adapted:

- it raises each listed row to at least the listed weight and never lowers one, so
  an upstream count that grows past ours is kept;
- other readings of the same text and every other row stay as upstream wrote them;
- a listed row that is missing, or that appears more than once, stops the build with
  `local-additions-weight-missing:<text>` / `local-additions-weight-ambiguous:<text>`
  for review;
- the result (table, weight before and after) goes into
  `local-additions-receipt.json` in the corresponding-source archive.

The locked recipe and its hash are unchanged. The weights are in the shared
`wanxiang` table, so they apply to 26-key and nine-key alike.

## Word list

Each phrase is raised only as far as it takes to come first on nine-key for its full
digits (是的 and 在的 also for the reported short form 7443 / 9243; 在吗 only to
second, behind 在哪), measured with
ReRime's harness; the measurements are in the ReRime IME-545 record.

| Phrase | Reading | Upstream | Raised to | Why (nine-key digits before the change) |
| --- | --- | --- | --- | --- |
| 是的 | shì de | 2,727 | 260,000 | Report (IME-530): 7443 must offer 是的 first; it competes with 是否 (213,074) and 四个 (42,848, whole reading), and 74433 with 十分 (66,672). |
| 在的 | zài de | 2,830 | 60,000 | Report (IME-530): 9243 should offer 在的 first, behind 再到 (30,298) and 压根 (16,092, whole reading) today. |
| 对的 | duì de | 386 | 8,000 | Chat reply; 38433 shows 对等 (3,721, completed) and 对风 first. Kept low: at 50,000 it split 团队的 in a nine-key sentence. |
| 行的 | xíng de | 4,311 | 15,000 | Chat reply; 946433 shows 赢得 (11,561, same digits) first. |
| 是啊 | shì a | 8,990 | 100,000 | Chat reply; 7442 shows 市场 (252,352, completed) and 失败 first. |
| 对啊 | duì a | 3,272 | 60,000 | Chat reply; 3842 shows 对比 (137,893, completed) first. |
| 好啊 | hǎo a | 5,668 | 30,000 | Chat reply; 4262 shows 好处 (51,301, completed) first. |
| 是吧 | shì ba | 14,438 | 30,000 | Chat reply; 74422 shows 失败 (58,781, completed) first. |
| 在吗 | zài ma | 0 | 15,000 | Chat greeting; upstream weight 0, so 92462 lists it 21st behind 在哪 (20,322) and 在那 (11,985, same digits). Raised to second only: 在哪 is as common in chat. |
| 在呢 | zài ne | 1,323 | 20,000 | Chat reply; 92463 shows 在内 (22,071, completed) first. |
| 好呢 | hǎo ne | 2,415 | 15,000 | Chat reply; 42663 shows 好么 (7,611, same digits) first. |
| 多谢 | duō xiè | 3,146 | 20,000 | Chat thanks; 386943 shows 多一点 first. |
| 稍等 | shāo děng | 634 | 20,000 | Chat phrase; 74263364 shows 前锋 (12,161, same digits) and 山峰 first. |
| 麻烦了 | má fan le | 1,429 | 30,000 | Chat phrase; 6232653 shows 拿到了 (24,922, same digits) first. |
| 拜拜 | bái bái | 4,192 | 15,000 | Chat farewell; 224224 shows 白菜 (5,787, same digits) first. |
| 您好 | nín hǎo | 5,994 | 30,000 | Greeting; 646426 shows 敏感 (14,475, same digits) first. |

Checked and left alone: 好的 (167,638) and 今天 (190,827) already come first once tail
completion is on (5468 now offers 今天 before 李牧). Not raised because the competitor
on the same digits is as common: 谢谢 / 这些 (943943), 干嘛 / 好吗, 早安 / 晚安,
走了 / 有了, 恭喜 / 工资, 呵呵 / 各个; learning ranks them for each user once chosen.

## Verification

- `tests/test_local_additions.py` covers raising, never lowering, leaving other
  readings alone, idempotence, a missing or repeated row stopping the build, and the
  shape of every listed entry.
- Ranking (nine-key and 26-key, before and after) is measured in ReRime
  (`nine-key.ranking-benchmark` and the IME-545 record), not in this repository.
