# trialyzer

An idea I had for a keyboard layout analyzer. It includes a specialized trigram typing test to allow users to measure their speed on arbitrary trigrams, and uses that data as the basis for layout analysis.

![Trialyzer's typing test in action](/misc/typingtest_image_3.png)

I'm also using this project as an opportunity to learn Python. This is my first time using Python for anything more substantial than CodingBat, and also my first project in VS Code, so things may be somewhat messy.

Uses Python packages:
- `pynput`
- `curses` (on windows, use `windows-curses`)

Usage:
- Once you have the above packages installed in your environment, run `trialyzer.py`.
    - I'll probably get around to a requirements.txt eventually maybe possibly.
- Trialyzer requires a pretty big console window for certain features. If you get a curses error, you may have to increase your window size and/or decrease font size.

Features:
- Layout analysis based on typing data provided by and personally applicable to you
- A large variety of bigram and trigram statistics, accounting for both frequency and your measured ease of typing each
- Autosuggest trigrams to use in the typing test to most effectively characterize a layout's common finger movements
- Estimate the physical typing speed limit of each layout based on your typing data
- Rank layouts by a large variety of different statistics
- Custom layouts, fingermaps, and even physical board definitiens can be added in files

Planned:
- Layout generation/optimization
- Heatmaps based on a variety of statistics
- More fingermaps, boards, layouts
- Alt fingering and sliding (maybe with some kind of customizable tag?)
- Shift layers/multiple characters per key
- Best and worst ngrams of each category

## Motivation

Recent analyzers such as [genkey](https://github.com/semilin/genkey) have included novel analysis concepts such as fingerspeed, in addition to the common bigram, trigram, and generalized n-gram stats (frequency of same finger bigrams/skipgrams, neighbor finger bigrams, lateral stretch bigrams, alternation, rolls, onehands, and redirects). However, in evaluating the overall fitness of a layout, the relative weights of all these different statistics generally must be selected arbitrarily. A noteworthy exception is that [semi](https://github.com/semilin) partially determined his weights by [using a script](https://semilin.github.io/semimak/#orgb1cc038) to measure the physical typing speed of each finger on selected same finger bigrams, and used that data to weight how bad sfb's are on each finger. This started me thinking.

Much discussion has been had about whether different movements are better or worse - for example, some people absolutely despise redirects, whereas others report being able to tolerate them quite well. A complicating factor is that not all redirects are equal; redirects involving ring and pinkies (such as the infamous `you` on Colemak) seem particularly bad. But how bad? Surely it depends on the exact key sequence? Similar questions can be asked about a wide range of other statistics: inward versus outward rolling, neighbor finger rowjumps, rolling versus alternation, and on and on.

**The goal of this analyzer is to use actual measured typing speed data to answer these questions, and more:**

- Have you been suspecting that your right ring finger is faster than your left? 
- Is QWERTY's `ve` roll tolerable until you add `x` afterward? 
- How bad is Colemak's `you` really, compared to the average redirect? Compared to `oyu`?

![Some stats shown after a bit of data collection](/misc/stats_image_1.png)

Instead of taking same finger bigrams, skipgrams, rolls, and all those other stats, and combining them into an overall layout fitness using arbitrary weights, it is my hope that the trigram speed statistic will naturally incorporate the effects of all these stats into one overall layout speed score, with no arbitrary weight selection required. However, we wouldn't be giving up the granularity of all those specific stats. In fact, we would be able to obtain *more* insight into, for example, exactly how bad each different sfb is, and how much they slow you down compared to the average non-sfb.

Here is an example of the kinds of insight trialyzer might be able to provide (with fictitious numbers):

- For layout A, the average keystroke time is 51.62 ms, giving a theoretical speed cap of 465 wpm. Of that average keystroke time, 8.16 ms (15.8%) is from redirects, which occur with a frequency of 6.89%.
- For layout B, the average keystroke time is 55.30 ms, giving a theoretical speed cap of 434 wpm. Of that average keystroke time, 7.02 ms (12.7%) is from redirects, which occur with a frequency of 7.03%.
- Therefore, we can say that layout B has more redirects than layout A, but those redirects aren't as bad. Perhaps we could break down the stats further to discover that layout A has redirects concentrated in the ring and pinky fingers, while layout B has redirects concentrated in the index and middle fingers. Or maybe one layout has redirects that jump between rows, and the other doesn't.

Of course, this approach comes with some limitations and drawbacks. 

- Speed is an objective measurement, but is it a good heuristic for comfort? It makes sense that they would be correlated, especially considering the results that have come out of the fingerspeed metric, but comfort is notoriously difficult to quantify. 
    - For example, you might be able to type a lateral stretch bigram quickly, but that doesn't mean it's comfortable. 
    - Or, how does the workload of each finger weigh in? Fatigue may be reflected in a longer test, or your finger may be slowly strained to unhealthy levels over the course of weeks, but certainly not when typing one trigram at a time.
- Considering just the main 30 keys of the keyboard, the number of possible trigrams is 27,000 - a very tedious number to sit through and test out one at a time, not even considering the number row, thumbs, and modifiers! 
    - To help mitigate this, trialyzer is able to analyze layouts even with incomplete trigram speed data (by extrapolating from what data it does have), so you won't be forced to test through every single trigram before getting any use out of it. This effect is shown as an "exactness" score that is displayed for certain stats.
    - Of course, extrapolation is never as good as actual complete data, so the more you test, the better the results will be. 

## Terminology

**Layout**  
A mapping between key names (`a`, `;`, `LShift`) and key positions (row, column). A fingermap and board are also specified for each layout. Examples: `QWERTY`, `colemak_dh`.

**Fingermap**  
A mapping between key positions (row, column) and fingers (`LI` for left index, `RP` for right pinky.) Examples: `traditional`, `angle_iso`.

**Board**  
A mapping between key positions (row, column) and physical locations of the keys (x/y coordinates). Examples: `iso`, `ortho`. 

**Bigram, trigram, n-gram**  
Existing terminology meaning a sequence of characters or key names. These may be called "text n-grams" to further clarify that they refer only to key names, which may vary depending on layout, as opposed to physical keys on the board.

**Bistroke, tristroke, n-stroke**  
A sequence of physical key locations on the board, each associated with the finger used for that key. Trialyzer collects data on the typing speeds of different tristrokes using its built-in typing test, then applies it to analyze a selected layout by associating those tristrokes with text trigrams.

(Note: Different fingermap-board combinations may have some tristrokes in common; for instance, all tristrokes involving the top and home row are identical between `traditional`-`ansi` and `angle_iso`-`iso`. Moreover, though the right hand is in a different position in `angle_iso` versus `angle_wide_iso`, the shape of each tristroke on the right hand is identical. Trialyzer accounts for these commonalities, and allows the relevant typing speed data to be shared between different boards and fingermaps.)

## Nstroke categories

### Subcategories

These subcategories are ways to further distinguish the major categories in the next sections.

**inward, outward**  
This is based on the *fingers* used for a series of keys. **Inward** means a finger closer to the pinky is used earlier, and a finger closer to the thumb is used later. **Outward** means the opposite. (Think of where the keys are located on the physical board.)

**skipgram/skipstroke**  
This refers to the bigram/bistroke formed by the first and third keys in a trigram/tristroke.

**scissor**  
This is when neighboring fingers are used to strike keys that are a distance of at least 2 apart on the board (Euclidean distance). Nstrokes with scissors tend to be slower and less comfortable than non-scissors.
- **In tristrokes,** scissors may occur between the first and second keypresses, or between the second and third. If both occur, the tristroke is categorized as `scissor.twice`. A scissor may also occur in the skipstroke, as with `b` and `e` in qwerty's `bae`, in which case the tristroke is categorized as `scissor_skip`. Finally, there is `scissor_and_skip`, which indicates that both a regular scissor and a `scissor_skip` are present.

### Bistroke categories

**alt**  
A bistroke using both hands.

**roll**  
A bistroke using one hand.

**sfr (same finger repeat)**  
A bistroke where the same finger is used twice to strike the same key.

**sfb (same finger bigram)**  
A bistroke where the same finger is used twice to strike different keys.

### Tristroke categories

**alt**  
A tristroke where you switch hands twice. Another way to think about it is that the first and third keys are struck with one hand, while the second key is struck with the other hand. Must not use the same finger more than once.

**roll**  
A tristroke where you switch hands once. Another way to think about it is that the first and third keys are struck with different hands. Must not use the same finger more than once.

**onehand**  
A tristroke typed entirely with the same hand, and which is entirely inward or entirely outward. Must not use the same finger more than once.

**redirect**  
A tristroke typed entirely with the same hand, and which is a mix of inward and outward. Must not use the same finger more than once.

**sft (same finger trigram)**  
A tristroke that uses the same finger for all three keys.

**sfr (same finger repeat)**  
A tristroke that uses the same finger twice in a row to strike the same key. Must not be an **sft**.  
- Subcategories of **sfr** are based on what happens with the remaining key - if there is a hand change, it is **sfr.alt**; if not, it is **sfr.roll**.

**sfb (same finger bigram)**  
A tristroke that uses the same finger twice in a row to strike different keys. Must not be an **sft**. 
- Subcategories of **sfb** are based on what happens with the remaining key - if there is a hand change, it is **sfb.alt**; if not, it is **sfb.roll**.

**sfs (same finger skipgram)**  
A tristroke that uses the same finger for the first and third keys. Must not be an **sft**. 
- Subcategories of **sfs** are based on what happens with the middle key - if it is on the other hand, the subcategory is **sfs.alt**; if it is on the same hand, the tristroke is **sfs.trill** if the first and third key are the same, and **sfs.redirect** if not.
