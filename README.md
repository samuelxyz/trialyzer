# trialyzer

An idea I had for a keyboard layout analyzer. It includes a specialized trigram typing test to allow users to measure their speed on arbitrary trigrams, and uses that data as the basis for layout analysis.

If you aren't familiar with the concept of alternate keyboard layouts, the short explanation is this: Imagine shuffling around the keys on the keyboard so they no longer read `QWERTY`. It seems reasonable to say that some of these arrangements are somehow "better" than others--more comfortable, or potentially faster to type on. The most widely known examples of alternate keyboard layouts include [Dvorak](https://en.wikipedia.org/wiki/Dvorak_keyboard_layout) and [Colemak](https://colemak.com), of which the latter is regarded more favorably in modern analysis. Trialyzer is a tool to help analyze and generate such layouts.

![Some images of trialyzer in action](/misc/medley_1.png)

I'm also using this project as an opportunity to learn Python. This is my first time using Python for anything more substantial than CodingBat, and also my first project in VS Code, so things may be somewhat messy.

Uses Python 3.10 with the following packages:
- `pynput`
- `windows-curses` (only needed if you're on Windows)

Usage:
- Once you have the above packages installed in your environment, use Python to run `trialyzer.py`.
    - I'll probably get around to a requirements.txt and other things eventually maybe possibly.
- Trialyzer runs in a terminal window. For best results, use a terminal that is capable of colors. 
    - A pretty big terminal window is needed for certain features. If you get a curses error, you may have to increase your window size and/or decrease font size.

Features:
- Layout analysis, comparison, and editing, based on typing data provided by and personally applicable to you
- A large variety of bigram and trigram statistics, accounting for both frequency and your measured ease of typing each
- Autosuggest trigrams to use in the typing test to most effectively characterize a layout's common finger movements
- Estimate the physical typing speed limit of each layout based on your typing data
- Rank layouts by a large variety of different statistics
- Draw layout heatmaps using a large variety of different statistics
- Custom layouts, fingermaps, and even physical board definitions can be added in files
- Layout optimization by simulated annealing and steepest ascent, with key pinning and usage constraints
- Load arbitrary text corpora with rules for shift and space keys

Planned:
- Further generation/optimization tools
- More fingermaps, boards, layouts
- Alt fingering and sliding, dynamic keys, layers

## What makes trialyzer special?

Recent analyzers such as [genkey](https://github.com/semilin/genkey) have included novel analysis concepts such as fingerspeed, in addition to the common bigram, trigram, and generalized n-gram stats (frequency of same finger bigrams/skipgrams, neighbor finger bigrams, lateral stretch bigrams, alternation, rolls, onehands, and redirects). However, in evaluating the overall fitness of a layout, the relative weights of all these different statistics are generally set arbitrarily. A noteworthy exception is that [semi](https://github.com/semilin) partially determined his weights by [using a script](https://semilin.github.io/semimak/#orgb1cc038) to measure the physical typing speed of each finger on selected same finger bigrams, and used that data to weight how bad sfb's are on each finger. This started me thinking.

Much discussion has been had about whether different movements are better or worse - for example, some people absolutely despise redirects, whereas others report being able to tolerate them quite well. A complicating factor is that not all redirects are equal; redirects involving ring and pinkies (such as the infamous `you` on Colemak) seem particularly bad. But how bad? Surely it depends on the exact key sequence? Similar questions can be asked about a wide range of other statistics: inward versus outward rolling, neighbor finger rowjumps, rolling versus alternation, and on and on.

**The goal of this analyzer is to use actual measured typing speed data to answer these questions, and more:**

- Have you been suspecting that your right ring finger is faster than your left? 
- Is QWERTY's `ve` roll tolerable until you add `x` afterward? 
- How bad is Colemak's `you` really, compared to the average redirect? Compared to `oyu`?

![Trialyzer's typing test in action](/misc/typingtest_image_3.png)

Other analyzers take same finger bigrams, skipgrams, rolls, and all those other stats, and combine them into an overall layout fitness using arbitrary weights. Trialyzer takes your own *experimentally measured* typing speed data and uses it to build up an overall trigram speed statistic. This naturally incorporates the effects of all these stats into one overall layout speed score, with no arbitrary weight selection required. The predicted maximum typing speed of a layout should, hopefully, also be a good measurement for how comfortable it is to type on.

Despite only having one main statistic, we don't give up up the granularity of all those more specific stats. In fact, with all this data, we actually obtain *more* insight into, for example, exactly how bad each different sfb is, and how much they slow you down compared to the average non-sfb. Trialyzer contains tools to calculate and display these statistics.

Of course, this approach comes with some limitations and drawbacks: 

- Speed is an objective measurement, but is it a good heuristic for comfort? It makes sense that they would be correlated, especially considering the results that have come out of the fingerspeed metric, but comfort is notoriously difficult to quantify. 
    - For example, you might be able to type a lateral stretch bigram quickly, but that doesn't mean it's comfortable. 
    - Or, how does the workload of each finger weigh in? Fatigue may be reflected in a longer test, or your finger may be slowly strained to unhealthy levels over the course of weeks, but certainly not when typing one trigram at a time.
- Considering just the main 30 keys of the keyboard, the number of possible trigrams is 27,000 - a very tedious number to sit through and test out one at a time, not even considering the number row, thumbs, and modifiers! 
    - To help mitigate this, trialyzer is able to analyze layouts even with incomplete trigram speed data (by extrapolating from what data it does have), so you won't be forced to test through every single trigram before getting any use out of it. This effect is shown as an "exactness" score that is displayed for certain stats.
    - Trialyzer also includes a setting to use only the top *n* most common trigrams rather than the full 27,000, which makes it compute substantially faster at the cost of losing some fidelity.
    - Of course, extrapolation is never as good as actual complete data, so the more you test, the better the results will be. 
- Trigrams don't capture the entire flow of longer sequences. A quadgram might have an uncomfortable interaction between the first and fourth letters, which won't be captured by trialyzer.
    - On the plus side, trigrams are at least much better than the older bigram-only statistics, while remaining within practical limits. Longer sequences quickly become combinatorically problematic to test and calculate, with a much larger number of possibilities than even trigrams. Perhaps trigram data can be split apart and pieced back together to form approximate measurements for longer sequences, which wouldn't require extra data collection but would still be a computational burden... an idea for later, perhaps?

![The data trap (from xkcd)](https://imgs.xkcd.com/comics/data_trap_2x.png)

## Terminology

**Layout**  
A mapping between key names (`a`, `;`, `shift_l`) and key positions (row, column). A fingermap and board are also specified for each layout.  
Examples: `QWERTY`, `colemak_dh`.

**Fingermap**  
A mapping between key positions (row, column) and fingers (`LI` for left index, `RP` for right pinky.)  
Possible examples: `traditional`, `iso_angle`.

**Board**  
A mapping between key positions (row, column) and physical locations of the keys (xy coordinates).  
Possible examples: `ansi`, `ortho`, `moonlander`. 

**Bigram, trigram, n-gram**  
Existing terminology meaning a sequence of characters or key names. These may be called "text n-grams" to further clarify that they refer only to key names, which may vary depending on layout, as opposed to physical keys on the board.

**Bistroke, tristroke, n-stroke**  
A sequence of physical key locations on the board, each associated with the finger used for that key. Trialyzer collects data on the typing speeds of different tristrokes using its built-in typing test, then applies it to analyze a selected layout by associating those tristrokes with text trigrams.

(Note: Different fingermap-board combinations may have some tristrokes in common; for instance, all tristrokes involving the top and home row are identical between `traditional`-`ansi` and `iso_angle`-`iso`. Moreover, though the right hand is in a different position in `iso_angle` versus `iso_angle_wide`, the shape of each tristroke on the right hand is identical. Trialyzer accounts for these commonalities, and allows the relevant typing speed data to be shared between different boards and fingermaps.)

For much more terminology and detail, see the [wiki](https://github.com/samuelxyz/trialyzer/wiki)!

# Some results

## General results

After typing a few thousand trigrams, I had enough typing data to gather some interesting observations.

[Trigram speeds plot](https://media.discordapp.net/attachments/798600991221219340/1028750494199468162/medians-2.png)

In this plot, each point represents the median speed of one trigram, broken down into bigram parts (`the` breaks down into `th` and `he`, which don't necessarily take the same amount of time each). The speeds of the faster and slower parts determine the position of the point on the vertical and horizontal axes. So, faster overall trigrams are to the lower left, and "metronome" trigrams where both bigram parts are the same speed would fall on the main diagonal.

The full explanation of trigram categories is [here](https://github.com/samuelxyz/trialyzer/wiki/Nstroke-categories). Note that some categories have been lumped together, to avoid cluttering the plot with too many minor categories.

First, this data seems to confirm the popular opinion that 2-1 or 1-2 rolls are faster than full alternating trigrams. It also raises other observations that are more interesting.

Notably, redirects are highly variable. There are some very fast ones, and a few very slow ones. The fastest redirects can even be faster than most rolls, while a few slow ones are even worse than SFBs. Consider: QWERTY's `xad` is terrible, but `joi` is actually quite fast and comfortable. This variation stands opposed to the popular opinion that redirects are uniformly worse than alternation, though it should be kept in mind that I can only measure speed, not comfort.

DSFBs (labeled as "sfs" in the plot) are faster than SFBs, but not twice as fast. They might merit a heavier weighting than the traditional SFB/2. 

Using these measurements as weights for every individual trigram, my analyzer displays some very interesting preferences. It regularly spits out layouts with high rolls and redirects, while maintaining low sfb and very low (near Semimak level) dsfb. It nearly always produces home rows containing at least one lower-frequency letter - most often `c` or `l`. Some of its behavior sketches me out (strange finger usage, off-home pinky redirects etc), but that's to be expected when it's using weightings concerned with pure trigram speeds and nothing else. I generally wouldn't recommend using these layouts exactly as produced without any tweaking, but they are certainly thought-provoking.

## Thoughts on same finger skipgrams

![Table of trigram categories](https://i.imgur.com/OWzD7JY.png)

This is a table of trigram categories. For this section, we are interested in the `sfs` subcategories, which is my name for a DSFB in trigram form. `sfs.alt` is an alternating DSFB, the others are various forms of same-hand DSFBs.

- The `ms` column indicates the average number of milliseconds it took me to type a trigram of that category. Lower is faster. Note that for each trigram, I typed many trials of it and kept the median time. So, each number in the `ms` column is an average of those medians.

- The `n` column indicates how many distinct trigrams of that category I have typed. The last column indicates how many are possible on the keyboard (at least, when including the keys that I have set up the code for). These two together indicate a sort of completion score, how confident you should be in the `ms` score of a particular trigram category.

We can see that `sfs.alt` is indeed faster than the same-hand `sfs` categories. However, note that even `sfs.alt` is substantially worse than your average redirect or alternating trigram, and much worse than rolls. In fact, `sfs` overall is the worst trigram category that doesn't contain consecutive same-finger use, by quite a wide margin.

DSFB is slightly less bad when it's alternating, but even then it's still a significant issue. 

Next, let's apply those speeds to a real layout, in this case Colemak.

![Example analysis](https://i.imgur.com/iAunwco.png)

The main thing that has happened here is that we have taken our median time for each trigram, and weighted it by the frequency of that trigram in the corpus (in this case, the typeracer quotes corpus). Some of the more detailed categories have been hidden for brevity, but we still have our main `sfs` categories visible.

- The `freq` column shows the total frequency of each trigram category in the corpus.

- the `exact` column shows the proportion of trigrams in each category (weighted by frequency of each individual trigram) that have exact speed data recorded. The rest have their speeds estimated from existing data by various means. You can think of this as a *lower bound* on how confident the analyzer is about the values in the next two columns. In my experience, once this score passes about 10%, the analyzer's extrapolations for unknown trigrams tend to be surprisingly accurate.

- The `avg_ms` column lists the average number of milliseconds taken to type a trigram of each category, weighted by frequency of each trigram within the category. You can think of this as a score describing how slow each category tends to be.

- The `ms` column is `avg_ms` weighted by the frequency of each category in the corpus. You can think of this as a score describing how much each category contributes to the whole layout's overall typing slowness.

Looking at the `avg_ms` column, we see that the typical `sfs` is worse than any non-same-finger, non-scissoring trigram. Worse than alternating, rolling, and redirecting trigrams. Looking at the `ms` column, we see that it also impacts the total typing time *more* than redirects. It also has more impact than trigrams containing sfbs. This makes sense because it's much more difficult to minimize dsfb than sfb, so there is substantially more dsfb in most layouts, Colemak included. So, decreasing dsfb may be a substantial opportunity to improve a layout's performance overall.
