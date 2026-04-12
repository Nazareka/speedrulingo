export type TileInstance = {
  id: string;
  text: string;
};

export function buildTileInstances(tiles: Array<string>): Array<TileInstance> {
  const counts = new Map<string, number>();
  return tiles.map((tile) => {
    const count = counts.get(tile) ?? 0;
    counts.set(tile, count + 1);
    return {
      id: `${tile}-${count}`,
      text: tile,
    };
  });
}

export function stableShuffle<T>(items: Array<T>, seed: string): Array<T> {
  return items
    .map((item, index) => {
      let hash = 2166136261;
      const input = `${seed}:${index}:${String(item)}`;
      for (let i = 0; i < input.length; i += 1) {
        hash ^= input.charCodeAt(i);
        hash = Math.imul(hash, 16777619);
      }
      return { item, hash: hash >>> 0 };
    })
    .sort((left, right) => left.hash - right.hash)
    .map(({ item }) => item);
}
