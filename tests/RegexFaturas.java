import java.util.regex.Pattern;

// Matcher.find usa a mesma semântica de regex Java utilizada pelo Spark rlike.
class RegexFaturas {
    public static void main(String[] args) {
        Pattern pattern = Pattern.compile(args[0]);
        for (int i = 1; i < args.length; i++) {
            System.out.println(pattern.matcher(args[i]).find());
        }
    }
}
