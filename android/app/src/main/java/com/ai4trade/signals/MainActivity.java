package com.ai4trade.signals;

import android.annotation.SuppressLint;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.graphics.Bitmap;
import android.net.Uri;
import android.os.Bundle;
import android.view.View;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

import androidx.activity.OnBackPressedCallback;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.splashscreen.SplashScreen;
import androidx.swiperefreshlayout.widget.SwipeRefreshLayout;

/**
 * Thin native shell that hosts the AI4Trade Signals PWA (https://aicompareapi.com/).
 * Chosen over a Trusted Web Activity because Huawei devices ship without Google
 * Mobile Services / Chrome, so a plain WebView is the reliable path on AppGallery.
 */
public class MainActivity extends AppCompatActivity {

    private static final String START_URL = "https://aicompareapi.com/?src=huawei";
    // Hosts we keep inside the app; everything else opens in an external browser/app.
    private static final String[] IN_APP_HOSTS = {
            "aicompareapi.com", "buy.stripe.com", "checkout.stripe.com", "js.stripe.com"
    };

    private WebView webView;
    private SwipeRefreshLayout refreshLayout;
    private View offlineView;
    private boolean loadError = false;

    @SuppressLint("SetJavaScriptEnabled")
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        SplashScreen.installSplashScreen(this);
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        refreshLayout = findViewById(R.id.refresh);
        webView = findViewById(R.id.webview);
        offlineView = findViewById(R.id.offline);
        findViewById(R.id.retry).setOnClickListener(v -> reload());

        WebSettings s = webView.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);           // PWA stores trial/subscription state here
        s.setDatabaseEnabled(true);
        s.setCacheMode(WebSettings.LOAD_DEFAULT);
        s.setLoadWithOverviewMode(true);
        s.setUseWideViewPort(true);
        s.setSupportZoom(false);
        s.setMediaPlaybackRequiresUserGesture(true);
        s.setUserAgentString(s.getUserAgentString() + " AI4TradeSignals/" + BuildConfig.VERSION_NAME);

        webView.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                return handleUrl(request.getUrl());
            }

            @Override
            public void onPageStarted(WebView view, String url, Bitmap favicon) {
                loadError = false;
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                refreshLayout.setRefreshing(false);
                if (loadError) {
                    showOffline(true);
                } else {
                    showOffline(false);
                }
            }

            @Override
            public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                // Only treat a failure of the main frame as an offline state.
                if (request.isForMainFrame()) {
                    loadError = true;
                }
            }
        });

        refreshLayout.setOnRefreshListener(this::reload);
        refreshLayout.setColorSchemeColors(0xFF3B82F6, 0xFF22C55E);

        getOnBackPressedDispatcher().addCallback(this, new OnBackPressedCallback(true) {
            @Override
            public void handleOnBackPressed() {
                if (webView.canGoBack()) {
                    webView.goBack();
                } else {
                    setEnabled(false);
                    getOnBackPressedDispatcher().onBackPressed();
                }
            }
        });

        if (savedInstanceState != null) {
            webView.restoreState(savedInstanceState);
        } else {
            webView.loadUrl(START_URL);
        }
    }

    private boolean handleUrl(Uri uri) {
        String scheme = uri.getScheme();
        if (scheme == null) return false;
        if (scheme.equals("http") || scheme.equals("https")) {
            String host = uri.getHost();
            if (host != null) {
                for (String allowed : IN_APP_HOSTS) {
                    if (host.equals(allowed) || host.endsWith("." + allowed)) {
                        return false; // load inside the WebView
                    }
                }
            }
        }
        // mailto:, tel:, intent:, and off-site links -> hand off to the system.
        try {
            startActivity(new Intent(Intent.ACTION_VIEW, uri));
        } catch (ActivityNotFoundException ignored) {
            return false;
        }
        return true;
    }

    private void reload() {
        showOffline(false);
        webView.reload();
    }

    private void showOffline(boolean show) {
        offlineView.setVisibility(show ? View.VISIBLE : View.GONE);
        refreshLayout.setVisibility(show ? View.GONE : View.VISIBLE);
        refreshLayout.setRefreshing(false);
    }

    @Override
    protected void onSaveInstanceState(Bundle outState) {
        super.onSaveInstanceState(outState);
        webView.saveState(outState);
    }

    @Override
    protected void onPause() {
        super.onPause();
        webView.onPause();
    }

    @Override
    protected void onResume() {
        super.onResume();
        webView.onResume();
    }
}
