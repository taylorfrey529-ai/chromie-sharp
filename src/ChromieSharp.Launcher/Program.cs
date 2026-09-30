using System.Net.Http.Json;
using System.Text.Json;
using Avalonia;
using Avalonia.Controls;
using Avalonia.Controls.ApplicationLifetimes;
using Avalonia.Layout;
using Avalonia.Styling;
using Avalonia.Themes.Fluent;

namespace ChromieSharp.Launcher;

internal static class Program
{
    [STAThread]
    public static void Main(string[] args) =>
        AppBuilder.Configure<App>().UsePlatformDetect().LogToTrace().StartWithClassicDesktopLifetime(args);
}

public sealed class App : Application
{
    public override void Initialize()
    {
        RequestedThemeVariant = ThemeVariant.Dark;
        Styles.Add(new FluentTheme());
    }

    public override void OnFrameworkInitializationCompleted()
    {
        if (ApplicationLifetime is IClassicDesktopStyleApplicationLifetime desktop)
            desktop.MainWindow = new MainWindow();
        base.OnFrameworkInitializationCompleted();
    }
}

public sealed class MainWindow : Window
{
    private readonly ChromieApiClient _api = new();
    private readonly TextBlock _mode = new() { FontSize = 13, FontWeight = Avalonia.Media.FontWeight.Bold };
    private readonly TextBlock _summary = new() { FontSize = 18, TextWrapping = Avalonia.Media.TextWrapping.Wrap };
    private readonly TextBlock _activity = new() { TextWrapping = Avalonia.Media.TextWrapping.Wrap };
    private readonly TextBlock _backend = new() { Text = "Backend: checking" };
    private readonly Button _play = new() { Content = "PLAY", Height = 58, FontSize = 20 };
    private readonly Button _repair = new() { Content = "REPAIR", Height = 40, IsVisible = false };
    private readonly Dictionary<string, TextBlock> _states = new(StringComparer.OrdinalIgnoreCase);
    private CancellationTokenSource? _operation;

    public MainWindow()
    {
        Title = "Chromie#";
        Width = 1180;
        Height = 740;
        MinWidth = 940;
        MinHeight = 620;

        var root = new Grid { ColumnDefinitions = new ColumnDefinitions("210,*") };
        root.Children.Add(BuildSidebar());

        var content = new StackPanel { Margin = new Thickness(34, 28), Spacing = 20 };
        Grid.SetColumn(content, 1);
        root.Children.Add(content);

        var header = new Grid { ColumnDefinitions = new ColumnDefinitions("*,Auto") };
        var title = new StackPanel { Spacing = 4 };
        title.Children.Add(new TextBlock { Text = "World of Warcraft", Opacity = 0.7 });
        title.Children.Add(new TextBlock { Text = "ChromieCraft 3.3.5a", FontSize = 32, FontWeight = Avalonia.Media.FontWeight.Bold });
        title.Children.Add(new TextBlock { Text = "Local private realm · Build 12340 target", Opacity = 0.65 });
        header.Children.Add(title);
        var refresh = new Button { Content = "REFRESH", Padding = new Thickness(18, 10), VerticalAlignment = VerticalAlignment.Top };
        refresh.Click += async (_, _) => await RefreshAsync();
        Grid.SetColumn(refresh, 1);
        header.Children.Add(refresh);
        content.Children.Add(header);

        var hero = new Border { Padding = new Thickness(24), CornerRadius = new CornerRadius(12) };
        var heroGrid = new Grid { ColumnDefinitions = new ColumnDefinitions("*,240") };
        var heroText = new StackPanel { Spacing = 8 };
        heroText.Children.Add(_mode);
        heroText.Children.Add(new TextBlock { Text = "Your realm, ready when you are.", FontSize = 24, FontWeight = Avalonia.Media.FontWeight.SemiBold });
        heroText.Children.Add(_summary);
        heroGrid.Children.Add(heroText);
        var heroButtons = new StackPanel { Spacing = 8, VerticalAlignment = VerticalAlignment.Center };
        _play.Click += async (_, _) => await RunOperationAsync("Launching realm…", _api.PlayAsync);
        _repair.Click += async (_, _) => await RunOperationAsync("Generating repair plan…", _api.RepairAsync);
        heroButtons.Children.Add(_play);
        heroButtons.Children.Add(_repair);
        Grid.SetColumn(heroButtons, 1);
        heroGrid.Children.Add(heroButtons);
        hero.Child = heroGrid;
        content.Children.Add(hero);

        var body = new Grid { ColumnDefinitions = new ColumnDefinitions("1.35*,*") };
        var statuses = new StackPanel { Spacing = 8 };
        statuses.Children.Add(new TextBlock { Text = "SYSTEM STATUS", FontWeight = Avalonia.Media.FontWeight.Bold, Opacity = 0.7 });
        foreach (var item in new[]
        {
            ("workbench", "Workbench"),
            ("database", "MariaDB"),
            ("authserver", "Auth Server"),
            ("worldserver", "World Server"),
            ("client", "ChromieCraft Client"),
            ("runtime", "Wine / DXVK"),
            ("display", "Display"),
        })
        {
            var row = new Grid { ColumnDefinitions = new ColumnDefinitions("*,Auto"), Margin = new Thickness(0, 4) };
            row.Children.Add(new TextBlock { Text = item.Item2 });
            var state = new TextBlock { Text = "—", FontWeight = Avalonia.Media.FontWeight.SemiBold };
            _states[item.Item1] = state;
            Grid.SetColumn(state, 1);
            row.Children.Add(state);
            statuses.Children.Add(row);
        }
        body.Children.Add(statuses);

        var activityBox = new Border { Padding = new Thickness(18), Margin = new Thickness(24, 0, 0, 0), CornerRadius = new CornerRadius(10) };
        var activityStack = new StackPanel { Spacing = 10 };
        activityStack.Children.Add(new TextBlock { Text = "ACTIVITY", FontWeight = Avalonia.Media.FontWeight.Bold, Opacity = 0.7 });
        activityStack.Children.Add(_activity);
        activityBox.Child = activityStack;
        Grid.SetColumn(activityBox, 1);
        body.Children.Add(activityBox);
        content.Children.Add(body);

        Content = root;
        Opened += async (_, _) => await RefreshAsync();
        Closed += (_, _) =>
        {
            CancelOperation();
            _api.Dispose();
        };
    }

    private Control BuildSidebar()
    {
        var panel = new StackPanel { Margin = new Thickness(22), Spacing = 16 };
        panel.Children.Add(new TextBlock { Text = "CHROMIE#", FontSize = 25, FontWeight = Avalonia.Media.FontWeight.Bold });
        panel.Children.Add(new TextBlock { Text = "PRIVATE REALM LAUNCHER", FontSize = 10, Opacity = 0.6 });
        panel.Children.Add(new TextBlock { Text = "GAME", Margin = new Thickness(0, 28, 0, 0), FontWeight = Avalonia.Media.FontWeight.SemiBold });
        panel.Children.Add(new TextBlock { Text = "SERVER", Opacity = 0.65 });
        panel.Children.Add(new TextBlock { Text = "REPAIR", Opacity = 0.65 });
        panel.Children.Add(new TextBlock { Text = "SETTINGS", Opacity = 0.65 });
        panel.Children.Add(new TextBlock { Text = "Chromie# 0.2-dev", Margin = new Thickness(0, 28, 0, 0), Opacity = 0.55 });
        panel.Children.Add(_backend);
        return new Border { Child = panel, Padding = new Thickness(0, 4), CornerRadius = new CornerRadius(0) };
    }

    private async Task RefreshAsync()
    {
        CancelOperation();
        _operation = new CancellationTokenSource();
        try
        {
            var snapshot = await _api.GetLauncherStatusAsync(_operation.Token);
            Apply(snapshot);
            _backend.Text = "Backend: connected";
        }
        catch (Exception ex) when (ex is HttpRequestException or TaskCanceledException)
        {
            _backend.Text = "Backend: unavailable";
            _mode.Text = "OFFLINE";
            _summary.Text = "Start the Chromie# Python backend to continue.";
            _activity.Text = ex.Message;
            _play.IsEnabled = false;
            _repair.IsVisible = false;
        }
    }

    private async Task RunOperationAsync(string activity, Func<CancellationToken, Task<ApiResult>> operation)
    {
        CancelOperation();
        _operation = new CancellationTokenSource();
        _play.IsEnabled = false;
        _activity.Text = activity;
        try
        {
            var result = await operation(_operation.Token);
            _activity.Text = result.Success ? result.Message ?? "Operation completed." : $"{result.ErrorCode}: {result.Message}";
            await RefreshAsync();
        }
        catch (Exception ex) when (ex is HttpRequestException or TaskCanceledException)
        {
            _activity.Text = ex.Message;
        }
    }

    private void Apply(LauncherSnapshot snapshot)
    {
        _mode.Text = snapshot.Mode;
        _summary.Text = snapshot.CanPlay
            ? "Core gates pass. Chromie# can start the realm and launch the client."
            : $"Repair required: {string.Join(", ", snapshot.RepairReasons)}";
        _play.Content = snapshot.CanPlay ? "PLAY" : "REPAIR REQUIRED";
        _play.IsEnabled = snapshot.CanPlay;
        _repair.IsVisible = !snapshot.CanPlay;

        foreach (var gate in snapshot.Gates)
        {
            if (_states.TryGetValue(gate.Key, out var state))
                state.Text = gate.Status.ToUpperInvariant();
        }
        _activity.Text = string.Join(Environment.NewLine, snapshot.Gates.Select(g => $"{g.Label}: {g.Message}"));
    }

    private void CancelOperation()
    {
        _operation?.Cancel();
        _operation?.Dispose();
        _operation = null;
    }
}

public sealed record LauncherGate(string Key, string Label, string Status, bool Blocking, string Message);
public sealed record LauncherSnapshot(string Mode, bool CanPlay, IReadOnlyList<LauncherGate> Gates, IReadOnlyList<string> RepairReasons);
public sealed record ApiResult(bool Success, string? ErrorCode, string? Message);

public sealed class ChromieApiClient : IDisposable
{
    private readonly HttpClient _http;

    public ChromieApiClient()
    {
        var baseUrl = Environment.GetEnvironmentVariable("CHROMIE_API_URL") ?? "http://127.0.0.1:5290/api/v1/";
        _http = new HttpClient { BaseAddress = new Uri(baseUrl, UriKind.Absolute), Timeout = TimeSpan.FromSeconds(35) };
    }

    public async Task<LauncherSnapshot> GetLauncherStatusAsync(CancellationToken cancellationToken = default)
    {
        using var response = await SendAsync(HttpMethod.Get, "launcher/status", cancellationToken);
        response.EnsureSuccessStatusCode();
        using var doc = JsonDocument.Parse(await response.Content.ReadAsStreamAsync(cancellationToken));
        var data = doc.RootElement.GetProperty("data");
        var gates = new List<LauncherGate>();
        foreach (var gate in data.GetProperty("gates").EnumerateArray())
        {
            gates.Add(new LauncherGate(
                gate.GetProperty("key").GetString() ?? "unknown",
                gate.GetProperty("label").GetString() ?? "Unknown",
                gate.GetProperty("status").GetString() ?? "unknown",
                gate.GetProperty("blocking").GetBoolean(),
                gate.GetProperty("message").GetString() ?? string.Empty));
        }
        var reasons = data.GetProperty("repair_reasons").EnumerateArray()
            .Select(x => x.GetString() ?? string.Empty)
            .Where(x => x.Length > 0)
            .ToArray();
        return new LauncherSnapshot(
            data.GetProperty("mode").GetString() ?? "REPAIR",
            data.GetProperty("can_play").GetBoolean(),
            gates,
            reasons);
    }

    public Task<ApiResult> PlayAsync(CancellationToken cancellationToken = default) =>
        InvokeAsync("launcher/play", cancellationToken);

    public Task<ApiResult> RepairAsync(CancellationToken cancellationToken = default) =>
        InvokeAsync("launcher/repair", cancellationToken);

    private async Task<ApiResult> InvokeAsync(string path, CancellationToken cancellationToken)
    {
        using var response = await SendAsync(HttpMethod.Post, path, cancellationToken);
        using var doc = JsonDocument.Parse(await response.Content.ReadAsStreamAsync(cancellationToken));
        var root = doc.RootElement;
        return new ApiResult(
            root.GetProperty("success").GetBoolean(),
            root.GetProperty("error_code").ValueKind == JsonValueKind.Null ? null : root.GetProperty("error_code").GetString(),
            root.GetProperty("message").ValueKind == JsonValueKind.Null ? null : root.GetProperty("message").GetString());
    }

    private Task<HttpResponseMessage> SendAsync(HttpMethod method, string path, CancellationToken cancellationToken)
    {
        var request = new HttpRequestMessage(method, path);
        request.Headers.Add("X-Request-Id", Guid.NewGuid().ToString());
        if (method == HttpMethod.Post)
            request.Content = JsonContent.Create(new { });
        return _http.SendAsync(request, cancellationToken);
    }

    public void Dispose() => _http.Dispose();
}
