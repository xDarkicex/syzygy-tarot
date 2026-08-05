/** Prints what the ORIGINAL Deck.java deals for a given seed, for fidelity testing. */
public class Harness {
  public static void main(String[] args) {
    int seed = Integer.parseInt(args[0]);
    int count = Integer.parseInt(args[1]);
    Deck deck = new Deck(seed);
    for (int i = 0; i < count; i++) {
      Card card = deck.draw();
      System.out.println(card.name + "\t" + card.reverse);
    }
  }
}
