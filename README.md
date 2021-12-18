# trialyzer

An idea I had for a keyboard layout analyzer. It includes a specialized trigram typing test to allow users to measure their speed on arbitrary trigrams, and uses that data as the basis for layout analysis.

![Trialyzer's typing test in action](/misc/typingtest_image_1.png)

I'm also using this project as an opportunity to learn Python. This is my first time using Python for anything more substantial than CodingBat, and also my first project in VS Code, so things may be somewhat messy.

Uses Python packages:
- `pynput`
- `curses` (on windows, use `windows-curses`)

## Motivation

Recent analyzers such as [genkey](https://github.com/semilin/genkey) have included novel analysis concepts such as fingerspeed, in addition to the common bigram, trigram, and generalized n-gram stats (frequency of same finger bigrams/skipgrams, neighbor finger bigrams, lateral stretch bigrams, alternation, rolls, onehands, and redirects). However, in evaluating the overall fitness of a layout, the relative weights of all these different statistics generally must be selected arbitrarily. A noteworthy exception is that [semi](https://github.com/semilin) partially determined his weights by [using a script](https://semilin.github.io/semimak/#orgb1cc038) to measure the physical typing speed of each finger on selected same finger bigrams, and used that data to weight how bad sfb's are on each finger. This started me thinking.

Much discussion has been had about whether different movements are better or worse - for example, some people absolutely despise redirects, whereas others report being able to tolerate them quite well. A complicating factor is that not all redirects are equal; redirects involving ring and pinkies (such as the infamous `you` on Colemak) seem particularly bad. But how bad? Surely it depends on the exact key sequence? Similar questions can be asked about a wide range of other statistics: inward versus outward rolling, neighbor finger rowjumps, rolling versus alternation, and on and on.

**The goal of this analyzer is to use actual measured typing speed data to answer these questions, and more:**

- Have you been suspecting that your right ring finger is faster than your left? 
- Is QWERTY's `ve` roll tolerable until you add `x` afterward? 
- How bad is Colemak's `you` really, compared to the average redirect? Compared to `oyu`?

Instead of taking same finger bigrams, skipgrams, rolls, and all those other stats, and combining them into an overall layout fitness using arbitrary weights, it is my hope that the trigram speed statistic will naturally incorporate the effects of all these stats into one overall layout speed score, with no weights required. However, we wouldn't be giving up the granularity of all those specific stats. In fact, we would be able to obtain *more* insight into, for example, exactly how bad each different sfb is, and how much they slow you down compared to the average non-sfb.

Here is an example of just some of the insight trialyzer might be able to provide (with fictitious numbers):

- For layout A, the average keystroke time is 25.81 ms, giving a theoretical speed cap of 465 wpm. Of that average keystroke time, 4.08 ms (15.8%) is from redirects, which occur with a frequency of 6.89%.
- For layout B, the average keystroke time is 27.65 ms, giving a theoretical speed cap of 434 wpm. Of that average keystroke time, 3.51 ms (12.7%) is from redirects, which occur with a frequency of 7.03%.
- Therefore, we can say that layout B has more redirects than layout A, but those redirects aren't as bad. Perhaps we could break down the stats further to discover that layout A has redirects concentrated in the ring and pinky fingers, while layout B has redirects concentrated in the index and middle fingers.

Of course, this approach comes with some limitations and drawbacks. 

- Speed is an objective measurement, but is it a good heuristic for comfort? It makes sense that they would be correlated, especially considering the results that have come out of the fingerspeed metric, but comfort is notoriously difficult to quantify. 
    - For example, you might be able to type a lateral stretch bigram quickly, but that doesn't mean it's comfortable. 
    - Or, how does the workload of each finger weigh in? Fatigue may be reflected in a longer test, or your finger may be slowly strained to unhealthy levels over the course of weeks, but certainly not when typing one trigram at a time.
- Considering just the main 30 keys of the keyboard, the number of possible trigrams is 27,000 - a very tedious number to sit through and test out one at a time, not even considering the number row, thumbs, and modifiers! 
    - To help mitigate this, trialyzer will be able to analyze layouts even with incomplete trigram speed data, allowing you to build up your statistics over time instead of having to test through every single trigram first. 
    - Additionally, as development progresses and we start measuring real data, it may turn out that only same-hand trigrams really show variation, while all alternating bigrams take roughly the same time. Or maybe you could mirror the trigrams of one hand to get a good approximation of the other hand's speeds. I don't know, I haven't seen that data yet! 

## Terminology

**Layout**  
A mapping between key names (`a`, `;`, `LShift`) and key positions (row, column). A fingermap is also specified. Examples: `qwerty`, `colemak_dh_ansi`.

**Fingermap**  
A mapping between key positions (row, column) and fingers (`LI` for left index, `RP` for right pinky.) Examples: `traditional`, `angle_iso`.

**Board**  
A mapping between key positions (row, column) and physical locations of the keys (x/y coordinates). Examples: `iso`, `matrix`. 

**Bigram, trigram, n-gram**  
Existing terminology meaning a sequence of characters or key names. These may be called "text n-grams" to further clarify that they refer only to key names, which may vary depending on layout, as opposed to physical keys on the board.

**Bistroke, tristroke, n-stroke**  
A sequence of physical key locations on the board, each associated with the finger used for that key. Trialyzer collects data on the typing speeds of different tristrokes using its built-in typing test, then applies it to analyze a selected layout by associating those tristrokes with text trigrams.

(Note: Different fingermap-board combinations may have some tristrokes in common; for instance, all tristrokes involving the top and home row are identical between `traditional`-`ansi` and `angle_iso`-`iso`. Moreover, though the right hand is in a different position in `angle_iso`-`iso` versus `angle_wide_iso`-`iso`, the shape of each tristroke on the right hand is identical. Trialyzer will detect these commonalities, and allow the relevant typing speed data to be shared between different boards.)