package com.ai4trade.signals;

import android.content.Intent;

import com.getcapacitor.JSArray;
import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

import com.huawei.hms.iap.Iap;
import com.huawei.hms.iap.IapApiException;
import com.huawei.hms.iap.entity.InAppPurchaseData;
import com.huawei.hms.iap.entity.IsEnvReadyResult;
import com.huawei.hms.iap.entity.OwnedPurchasesReq;
import com.huawei.hms.iap.entity.OwnedPurchasesResult;
import com.huawei.hms.iap.entity.ProductInfo;
import com.huawei.hms.iap.entity.ProductInfoReq;
import com.huawei.hms.iap.entity.ProductInfoResult;
import com.huawei.hms.iap.entity.PurchaseIntentReq;
import com.huawei.hms.iap.entity.PurchaseIntentResult;
import com.huawei.hms.iap.entity.PurchaseResultInfo;
import com.huawei.hms.support.api.client.Status;

import org.json.JSONException;

import java.util.ArrayList;
import java.util.List;

/**
 * HMS In-App Purchases bridge — subscriptions.
 *
 * Implements the contract consumed by src/lib/hms/iap.ts:
 *   isEnvReady()      -> { ready: boolean }
 *   queryProducts()   -> { products: IapProduct[] }
 *   purchase()        -> { purchase: IapPurchase }
 *   restorePurchases()-> { purchases: IapPurchase[] }
 *
 * priceType 2 == SUBSCRIPTION in HMS IAP.
 */
@CapacitorPlugin(name = "HmsIap")
public class HmsIapPlugin extends Plugin {

    private static final int PRICE_TYPE_SUBSCRIPTION = 2;
    private static final int REQ_CODE_PURCHASE = 6001;

    /** Callback id of the in-flight purchase() call awaiting the HMS UI result. */
    private String pendingPurchaseCallId = null;

    @PluginMethod
    public void isEnvReady(final PluginCall call) {
        Iap.getIapClient(getActivity()).isEnvReady()
            .addOnSuccessListener(result -> {
                JSObject ret = new JSObject();
                ret.put("ready", true);
                call.resolve(ret);
            })
            .addOnFailureListener(e -> {
                JSObject ret = new JSObject();
                ret.put("ready", false);
                call.resolve(ret);
            });
    }

    @PluginMethod
    public void queryProducts(final PluginCall call) {
        JSArray ids = call.getArray("productIds");
        List<String> productIds = new ArrayList<>();
        try {
            for (int i = 0; i < ids.length(); i++) {
                productIds.add(ids.getString(i));
            }
        } catch (JSONException e) {
            call.reject("Invalid productIds", e);
            return;
        }

        ProductInfoReq req = new ProductInfoReq();
        req.setPriceType(PRICE_TYPE_SUBSCRIPTION);
        req.setProductIds(productIds);

        Iap.getIapClient(getActivity()).obtainProductInfo(req)
            .addOnSuccessListener(result -> {
                JSArray products = new JSArray();
                for (ProductInfo info : result.getProductInfoList()) {
                    JSObject p = new JSObject();
                    p.put("productId", info.getProductId());
                    p.put("price", info.getPrice());
                    p.put("currency", info.getCurrency());
                    p.put("title", info.getProductName());
                    products.put(p);
                }
                JSObject ret = new JSObject();
                ret.put("products", products);
                call.resolve(ret);
            })
            .addOnFailureListener(e -> call.reject("obtainProductInfo failed: " + e.getMessage(), e));
    }

    @PluginMethod
    public void purchase(final PluginCall call) {
        final String productId = call.getString("productId");
        if (productId == null) {
            call.reject("productId is required");
            return;
        }

        PurchaseIntentReq req = new PurchaseIntentReq();
        req.setPriceType(PRICE_TYPE_SUBSCRIPTION);
        req.setProductId(productId);

        Iap.getIapClient(getActivity()).createPurchaseIntent(req)
            .addOnSuccessListener(result -> {
                Status status = result.getStatus();
                if (status.hasResolution()) {
                    // HMS returns a PendingIntent-backed resolution. Save the
                    // Capacitor call so it can be resolved from
                    // handleOnActivityResult, then launch the HMS purchase UI.
                    bridge.saveCall(call);
                    pendingPurchaseCallId = call.getCallbackId();
                    try {
                        status.startResolutionForResult(getActivity(), REQ_CODE_PURCHASE);
                    } catch (Exception e) {
                        bridge.releaseCall(call);
                        pendingPurchaseCallId = null;
                        call.reject("Failed to start purchase flow: " + e.getMessage(), e);
                    }
                } else {
                    call.reject("Purchase intent has no resolution");
                }
            })
            .addOnFailureListener(e -> {
                if (e instanceof IapApiException) {
                    IapApiException api = (IapApiException) e;
                    if (api.getStatusCode() == com.huawei.hms.iap.entity.OrderStatusCode.ORDER_PRODUCT_OWNED) {
                        call.reject("You already own this subscription. Use Restore purchases.");
                        return;
                    }
                }
                call.reject("createPurchaseIntent failed: " + e.getMessage(), e);
            });
    }

    /**
     * Delivered when the HMS purchase UI returns. Parses the purchase data and
     * resolves the pending purchase() call.
     */
    @Override
    protected void handleOnActivityResult(int requestCode, int resultCode, Intent data) {
        super.handleOnActivityResult(requestCode, resultCode, data);
        if (requestCode != REQ_CODE_PURCHASE || pendingPurchaseCallId == null) {
            return;
        }
        PluginCall call = bridge.getSavedCall(pendingPurchaseCallId);
        pendingPurchaseCallId = null;
        if (call == null) {
            return;
        }
        if (data == null) {
            call.reject("Purchase cancelled");
            bridge.releaseCall(call);
            return;
        }
        PurchaseResultInfo info = Iap.getIapClient(getActivity()).parsePurchaseResultInfoFromIntent(data);
        switch (info.getReturnCode()) {
            case com.huawei.hms.iap.entity.OrderStatusCode.ORDER_STATE_SUCCESS:
                try {
                    InAppPurchaseData purchaseData = new InAppPurchaseData(info.getInAppPurchaseData());
                    JSObject purchase = new JSObject();
                    purchase.put("productId", purchaseData.getProductId());
                    purchase.put("purchaseToken", purchaseData.getPurchaseToken());
                    purchase.put("purchaseState", purchaseData.getPurchaseState());
                    // subValid: whether the subscription is currently valid.
                    purchase.put("active", purchaseData.isSubValid());
                    JSObject ret = new JSObject();
                    ret.put("purchase", purchase);
                    call.resolve(ret);
                } catch (JSONException e) {
                    call.reject("Failed to parse purchase data", e);
                }
                break;
            case com.huawei.hms.iap.entity.OrderStatusCode.ORDER_STATE_CANCEL:
                call.reject("Purchase cancelled");
                break;
            default:
                call.reject("Purchase failed (code " + info.getReturnCode() + ")");
                break;
        }
        bridge.releaseCall(call);
    }

    @PluginMethod
    public void restorePurchases(final PluginCall call) {
        OwnedPurchasesReq req = new OwnedPurchasesReq();
        req.setPriceType(PRICE_TYPE_SUBSCRIPTION);

        Iap.getIapClient(getActivity()).obtainOwnedPurchases(req)
            .addOnSuccessListener(result -> {
                JSArray purchases = new JSArray();
                List<String> dataList = result.getInAppPurchaseDataList();
                if (dataList != null) {
                    for (String raw : dataList) {
                        try {
                            InAppPurchaseData d = new InAppPurchaseData(raw);
                            JSObject p = new JSObject();
                            p.put("productId", d.getProductId());
                            p.put("purchaseToken", d.getPurchaseToken());
                            p.put("purchaseState", d.getPurchaseState());
                            p.put("active", d.isSubValid());
                            purchases.put(p);
                        } catch (JSONException ignored) {
                            // Skip malformed entries.
                        }
                    }
                }
                JSObject ret = new JSObject();
                ret.put("purchases", purchases);
                call.resolve(ret);
            })
            .addOnFailureListener(e -> call.reject("obtainOwnedPurchases failed: " + e.getMessage(), e));
    }
}
