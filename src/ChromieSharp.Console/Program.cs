using System.Net.Http.Json;
using System.Text.Json;

const string DefaultBaseUrl = "http://127.0.0.1:5290/api/v1/";
var baseUrl = Environment.GetEnvironmentVariable("CHROMIE_API_URL") ?? DefaultBaseUrl;
var command = args.FirstOrDefault()?.ToLowerInvariant() ?? "status";

var routes = new Dictionary<string, (HttpMethod Method, string Path)>(StringComparer.OrdinalIgnoreCase)
{
    ["health"] = (HttpMethod.Get, "health"),
    ["status"] = (HttpMethod.Get, "status"),
    ["start"] = (HttpMethod.Post, "server/start"),
    ["stop"] = (HttpMethod.Post, "server/stop"),
    ["restart"] = (HttpMethod.Post, "server/restart"),
    ["preflight"] = (HttpMethod.Get, "client/preflight"),
    ["launch"] = (HttpMethod.Post, "client/launch"),
    ["logs"] = (HttpMethod.Get, "logs?lines=100"),
};

if (!routes.TryGetValue(command, out var route))
{
    Console.Error.WriteLine("Usage: chromie [health|status|start|stop|restart|preflight|launch|logs]");
    return 64;
}

using var client = new HttpClient { BaseAddress = new Uri(baseUrl, UriKind.Absolute), Timeout = TimeSpan.FromSeconds(35) };
using var request = new HttpRequestMessage(route.Method, route.Path);
request.Headers.Add("X-Request-Id", Guid.NewGuid().ToString());
if (route.Method == HttpMethod.Post)
    request.Content = JsonContent.Create(new { });

try
{
    using var response = await client.SendAsync(request);
    var raw = await response.Content.ReadAsStringAsync();
    try
    {
        using var doc = JsonDocument.Parse(raw);
        Console.WriteLine(JsonSerializer.Serialize(doc.RootElement, new JsonSerializerOptions { WriteIndented = true }));
    }
    catch (JsonException)
    {
        Console.WriteLine(raw);
    }
    return response.IsSuccessStatusCode ? 0 : (int)response.StatusCode;
}
catch (Exception ex) when (ex is HttpRequestException or TaskCanceledException)
{
    Console.Error.WriteLine($"Chromie# backend unavaile: {ex.Message}");
    return 69;
}
