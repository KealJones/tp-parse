// Keal's solution, as it ended (from the screen recording, 2026-10-23). Works for n = 3 and n = 10.
function boustrophedonGrid(n: number) {
  let count = 1;
  const grid = [] as number[][];
  for (let row = 0; row < n; row++) {
    grid.push(new Array<number>());
    for (let i = 1; i <= n; i++) {
      grid[row].push(count++);
    }
    if (row % 2) {
      grid[row].reverse();
    }
  }
  grid.forEach((row) => row.join(' '));   // no effect (result discarded), so rows print with commas
  return grid.join('\n');
}

console.log(boustrophedonGrid(10));
