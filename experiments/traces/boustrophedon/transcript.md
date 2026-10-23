# Audio Transcription: videos_in_order_audio_2.mp3

[00:00] Okay, so I'm starting your task here. Um, I get out last night. That's for a prompt, blah blah, problem: Write a function that takes a n, a number n, and prints the numbers uh 1 to n squared in a square grid laid out boustrophedon.

[00:22] Okay. I've no idea what the fuck boustrophedon is, so I guess that's the first thing I'm gonna do is uh define boustrophedon. It is an ancient writing style where alternate lines of text run in opposite... oh fuck me. Okay. Moving left to right on one line and right to left on the next. Okay, that's easy enough. I think, maybe.

[00:46] Often with the individual letters mirrored in the reverse letters. In reverse lines. Uh, the the letters mirrored? I don't think I can do that. At least not in like normal text output. Uh, I'll do I'll get close enough and then I will mention that I can't do the letters mirrored thing.

[01:10] So like, actually this this is probably even easier just to do like um I can probably just do it in like the console if I really... I'm lazy, you know. Uh, go via JS... not JS Bin. Wow. I'm stupid. Okay. Fuck it, we're going back here. New file.

[01:32] It's been so long since I've written code that I actually like don't know how to just run some like arbitrary JavaScript. Um, I'm pretty sure I can run a terminal here and just do like node whatever this path is that I end up... Okay, so let's make the file. Save as... um, on my desktop I guess, and just call it uh boustrophedon.js or ts.

[01:52] I want to do it in TypeScript, but I actually think it'll be easier if I do it in JavaScript. Whatever. Okay, so function... uh, what was the question?

[02:05] Is this recording only works for like 10 or for 5 minutes and I'm already at like 2 minutes fuck. Okay. Um, takes a number n, right? Number, for sure. Um, and then...

[02:28] So my thinking process here is that so it goes uh it's going to be like a loop uh over however many... takes a number n and prints the numbers 1 to n squared in a square grid laid out boustrophedon. Okay.

[02:50] Okay, okay. So like my thought is basically to make a um a series of arrays. So like whatever n is, um the first array is like n or 1 to n. And then uh this clue here, the 3x3 grid, makes me think that the square is it is just a square, right? Right, that's why it's called... okay, cool.

[03:15] I'm not good at math. Claude, why don't you give me a math problem? Okay, so yeah no, here's what my idea is. We're gonna loop n times, right? So loop... I remember, I mean fuck, for uh const i... actually I don't even know how to do this. const i = 1, um i++.

[03:42] Going to be a little bit faster than this just because I'm a stupid human. Um, and then uh fuck, I don't even know how to do a for loop in... Okay. So I'm looking up how to do a for loop in JavaScript, which valid. If it didn't know how to do this, then you should do that.

[04:05] So, here this looks like a good one, basic incrementation. Yeah. I'm gonna copy that. Oh, look at that, there we go. Fucking JavaScript. Okay. And then now that I have let i blah blah, i plus... oh, i is less than or equal to uh n squared is n...

[04:32] I don't actually know how to do JavaScript. I don't actually know if there's like a very obvious math whatever. Uh, powers in math... Um, no, okay. JavaScript um number to power. Pow. Math.pow. Times times, does that work? Times times? Exponent operator, nice. I always use that one.

[05:00] So it'd be like n pow pow n, or n pow pow 2? n pow pow 2. I like that I call it bow pow. It's just star star, okay. Uh, n pow pow 2, right? That would be it.

[05:25] So then um I'm gonna create an array. Um, this is probably stupid the way I'm doing it, but whatever. Um, an array of arrays, right? So const uh fucking grid equals an array. And then for this um grid equal or grid.push... uh no, wait.

[05:55] Okay, wait. If i if i is less than n, then grid... or wait, if i... Son of a bitch. Okay, wait. I feel really stupid right now and it's kind of embarrassing.

[06:30] Okay, so then... And also what's really funny is I know that I'm not doing the best solution here. I know that there's a better one. Um, but okay.

[07:00] So uh let me think about this again. We need to loop from i to n n times. i to n n times, right? So then, okay, we also need a loop around this loop. Let uh I'm gonna do like for let row = 1, actually 0 'cause it's gonna be like an index of the grid that we're on.

[07:45] Um, while row is less than or equal to n, uh row++. Okay. Yeah yeah yeah yeah, we're cooking with oil now. Okay.

[08:25] And then this here, bloop bloop bam pow, I can actually put this grid um .push here of an empty array. Yep. Yep.

[10:05] Oh, has officially been over 10 minutes of me doing this. Okay. So uh then we can remove this here. Uh, push this in. And so then, what is wrong here? Cannot redeclare... oh. Um, okay. grid.push empty array.

[10:45] Um, okay, and so for while i is 1... Wait a minute. We're actually going to do 1 'cause we're not doing base-zero counting here. And then i = 1, i is less than n times that... oh no, i is less than n, not n to the exponent, right?

[11:30] So then we are going to just push... I'm like positive that there's a better way to do this. Um, okay, we're gonna get grid[row].push... I could probably use like a generator or something. Um, stupid fucking...

[12:15] No, don't use AI, fuck off. I don't know how to declare this as like a number array. This is the grossest syntax, too. Like, why... I don't... not good at this. New... Wait, what? What is a... Whatever, fuck off.

[12:55] Okay, and then um so there, now we have that. And then after it's done doing that, if row % 2, maybe like every other row, gonna do row or grid[row].reverse().

[13:35] And then at the end I'm going to uh console.log, or I mean I guess I should return, right? return um grid uh .join... Wait, no. How do you do nested... How do you do a sub... Fuck, okay. How do you do JavaScript um array of arrays?

[14:10] Actually, I'll just like grid.forEach row, row.join uh with like a space. And then does forEach return... no, it's void. So then grid.join new line. That should work, probably, right? Copy path, node, plop.

[15:00] It's now been 15 minutes. So okay. Ugh, stupid fucking...

[15:18] Mm-hmm, mm-hmm. I That totally makes sense probably, right, 'cause I didn't um do this console.log. So let's go with the 3 example.

[15:35] Okay. Oh right, because row is right right right, I meant 0. So then row + 1 'cause it's offset by like 0 now. Does that work?

[15:50] That is four lines. Uh, also it is not... Fuck me, dude, I'm so dumb. Okay. Right, so i can't just be less than... I need like a a a... Okay, let count = 0 or 1, and then count++. There, that should take care of that.

[16:08] Right. Okay, so then why is there a third line? row... Oh, because I'm doing row 0, so I just want this to be less than n, because offset by 1. And then the wrong lines are reversing, I believe.

[16:22] Moving left to right on one line and then left to right and then right to left. So yeah, this is backwards. So the % 2 is off. There we go, because the offsetting was actually correct. Okay.

[16:38] So: 1 2 3, 6 5 4, 7 8 9. That's it, right? I mean I probably could have made this a script that could like do more, but like... So if that's now 10... Yeah? I think. Yeah. Wait, no.

[16:52] Oh yeah, wait. 50, 60, 51... Wait, what? 50, wait, 50, 51, 60, 61. Okay yeah, no, it's going right. This is right. This is right. I did it. I did it! Time! Time!