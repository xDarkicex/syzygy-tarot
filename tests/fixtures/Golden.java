import java.util.*;

/** Emits golden fixtures so the Python port can be verified as bit-exact. */
public class Golden {
  static final int[] SEEDS = {0, 1, 7, 42, 123, 1000, 31337, -5, 2147483647};

  public static void main(String[] args) {
    // 1. Raw nextInt() / nextDouble() streams.
    for (int seed : SEEDS) {
      Random r = new Random(seed);
      StringBuilder ints = new StringBuilder();
      for (int i = 0; i < 5; i++) ints.append(r.nextInt()).append(i < 4 ? "," : "");
      Random r2 = new Random(seed);
      StringBuilder dbls = new StringBuilder();
      for (int i = 0; i < 3; i++) dbls.append(r2.nextDouble()).append(i < 2 ? "," : "");
      System.out.println("RAW\t" + seed + "\t" + ints + "\t" + dbls);
    }

    // 2. nextInt(bound) across power-of-two and non-power-of-two bounds.
    for (int seed : SEEDS) {
      for (int bound : new int[] {2, 3, 7, 16, 52, 78, 100}) {
        Random r = new Random(seed);
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < 6; i++) sb.append(r.nextInt(bound)).append(i < 5 ? "," : "");
        System.out.println("BOUND\t" + seed + "\t" + bound + "\t" + sb);
      }
    }

    // 3. Exactly what Deck.java does: shuffle a 78-card deck, then draw with reversals.
    for (int seed : SEEDS) {
      List<Integer> deck = new ArrayList<>();
      for (int i = 0; i < 78; i++) deck.add(i);
      Random rng = new Random(seed);
      Collections.shuffle(deck, rng);
      StringBuilder order = new StringBuilder();
      for (int i = 0; i < 78; i++) order.append(deck.get(i)).append(i < 77 ? "," : "");
      // Deck.draw(): remove(0) then setReverse(rng.nextDouble() > 0.5)
      StringBuilder rev = new StringBuilder();
      for (int i = 0; i < 10; i++) rev.append(rng.nextDouble() > 0.5).append(i < 9 ? "," : "");
      System.out.println("DECK\t" + seed + "\t" + order + "\t" + rev);
    }
  }
}
