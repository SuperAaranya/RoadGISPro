import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;

public class MetricsEngine {
    public static void main(String[] args) throws Exception {
        BufferedReader br = new BufferedReader(new InputStreamReader(System.in, StandardCharsets.UTF_8));
        StringBuilder sb = new StringBuilder();
        String line;
        while ((line = br.readLine()) != null) {
            sb.append(line);
        }
        String raw = sb.toString();

        int roadCount = countToken(raw, "\"rtype\"");
        int connectorCount = countToken(raw, "\"level_span\"");
        int onewayCount = countToken(raw, "\"oneway\":true");
        double onewayShare = roadCount == 0 ? 0.0 : ((double) onewayCount / roadCount);

        String json = "{"
                + "\"engine\":\"java\","
                + "\"road_count\":" + roadCount + ","
                + "\"connector_count\":" + connectorCount + ","
                + "\"total_length_km\":0.0,"
                + "\"average_speed_limit\":0.0,"
                + "\"average_lanes\":0.0,"
                + "\"oneway_share\":" + onewayShare
                + "}";
        System.out.println(json);
    }

    private static int countToken(String haystack, String needle) {
        int idx = 0;
        int count = 0;
        while (true) {
            idx = haystack.indexOf(needle, idx);
            if (idx < 0) break;
            count++;
            idx += needle.length();
        }
        return count;
    }
}
