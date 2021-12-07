# trialyzer

An idea I had for a keyboard layout analyzer. It includes a specialized trigram typing test to allow users to measure their speed on arbitrary trigrams, and uses that data as the basis for layout analysis.

I'm also using this project as an opportunity to learn Python. This is my first time using Python for anything more substantial than CodingBat, and also my first project in VS Code, so things may be somewhat messy.

## Motivation

Recent analyzers such as [genkey](https://github.com/semilin/genkey) have included novel analysis concepts such as fingerspeed, in addition to the common bigram, trigram, and generalized n-gram stats (frequency of same finger bigrams/skipgrams, neighbor finger bigrams, lateral stretch bigrams, alternation, rolls, onehands, and redirects). I found it particularly noteworthy that [semi](https://github.com/semilin) partially determined his weights by [using a script](https://semilin.github.io/semimak/#orgb1cc038) to measure the physical typing speed of each finger on selected same finger bigrams. However, many of the other weights had to be assigned arbitrarily, such as the relative weights of different movement distances, rolls versus alternation, the badness of redirects, and so on.

Much discussion has been had about whether different movements are better or worse - for example, some people absolutely despise redirects, whereas others report being able to tolerate them quite well. A complicating factor is that not all redirects are equal; redirects involving ring and pinkies (such as the infamous `you` on Colemak) seem particularly bad. A similar discussion can be had about a wide range of other statistics: inward versus outward rolling, neighbor finger rowjumps, rolling versus alternation, and on and on.

The goal of this analyzer is to use actual **measured typing speed data** to answer these questions, and more. 

- Have you been suspecting that your right ring finger is faster than your left? 
- Is QWERTY's `ve` roll tolerable until you add `x` afterward? 
- How bad is Colemak's `you` really, compared to the average redirect? Compared to `oyu`?

Of course, this approach comes with some limitations and drawbacks. 

- Speed is an objective mesaurement, but is it a good heuristic for comfort? It makes sense that they would be correlated, especially considering the results that have come out of the fingerspeed metric, but comfort is notoriously difficult to quantify. You might be able to type a lateral stretch bigram quickly, but that doesn't mean it's comfortable. Or, how does the workload of each finger weigh in? Fatigue may be reflected in a longer test, or your finger may be slowly strained to unhealthy levels over the course of weeks, but certainly not when typing one trigram at a time.
- Considering just the main 30 keys of the keyboard, the number of possible trigrams is 27,000 - a very tedious number to sit through and test out one at a time, not even considering the number row, thumbs, and modifiers! To help mitigate this, trialyzer will be able to analyze layouts even with incomplete trigram speed data, allowing you to build up your statistics over time instead of having to test through every single trigram first. Additionally, as development progresses and we start measuring real data, it may turn out that only same-hand trigrams really show variation, while all alternating bigrams take roughly the same time. Or maybe you could mirror the trigrams of one hand to get a good approximation of the other hand's speeds. I don't know, I haven't seen that data yet! 
