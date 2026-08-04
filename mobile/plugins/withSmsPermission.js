const { withAndroidManifest, withDangerousMod } = require('@expo/config-plugins');
const fs = require('fs');
const path = require('path');

const SMS_MODULE_KT = `package com.fasttrade.app

import android.content.ContentResolver
import android.database.Cursor
import android.net.Uri
import com.facebook.react.bridge.*
import org.json.JSONArray
import org.json.JSONObject

class SmsModule(reactContext: ReactApplicationContext) :
    ReactContextBaseJavaModule(reactContext) {

    override fun getName() = "SmsAndroid"

    @ReactMethod
    fun list(filterJson: String, fail: Callback, success: Callback) {
        try {
            val filter = JSONObject(filterJson)
            val maxCount = filter.optInt("maxCount", 200)
            val uri = Uri.parse("content://sms/inbox")
            val cr: ContentResolver = reactApplicationContext.contentResolver
            val cursor: Cursor? = cr.query(
                uri,
                arrayOf("address", "body", "date"),
                null, null,
                "date DESC LIMIT \$maxCount"
            )
            val result = JSONArray()
            cursor?.use {
                val addrIdx = it.getColumnIndex("address")
                val bodyIdx = it.getColumnIndex("body")
                val dateIdx = it.getColumnIndex("date")
                while (it.moveToNext()) {
                    val obj = JSONObject()
                    obj.put("address", it.getString(addrIdx) ?: "")
                    obj.put("body", it.getString(bodyIdx) ?: "")
                    obj.put("date", it.getLong(dateIdx))
                    result.put(obj)
                }
            }
            success.invoke(result.length(), result.toString())
        } catch (e: Exception) {
            fail.invoke(e.message)
        }
    }
}
`;

const SMS_PACKAGE_KT = `package com.fasttrade.app

import com.facebook.react.ReactPackage
import com.facebook.react.bridge.NativeModule
import com.facebook.react.bridge.ReactApplicationContext
import com.facebook.react.uimanager.ViewManager

class SmsPackage : ReactPackage {
    override fun createNativeModules(ctx: ReactApplicationContext): List<NativeModule> =
        listOf(SmsModule(ctx))

    override fun createViewManagers(ctx: ReactApplicationContext): List<ViewManager<*, *>> =
        emptyList()
}
`;

function withSmsPermission(config) {
  // 1. Add permissions to AndroidManifest
  config = withAndroidManifest(config, (cfg) => {
    const manifest = cfg.modResults.manifest;
    if (!manifest['uses-permission']) manifest['uses-permission'] = [];
    const perms = manifest['uses-permission'].map((p) => p.$?.['android:name']);
    if (!perms.includes('android.permission.READ_SMS'))
      manifest['uses-permission'].push({ $: { 'android:name': 'android.permission.READ_SMS' } });
    if (!perms.includes('android.permission.RECEIVE_SMS'))
      manifest['uses-permission'].push({ $: { 'android:name': 'android.permission.RECEIVE_SMS' } });
    return cfg;
  });

  // 2. Write SmsModule.kt + SmsPackage.kt and patch MainApplication.kt
  config = withDangerousMod(config, [
    'android',
    (cfg) => {
      const javaDir = path.join(
        cfg.modRequest.platformProjectRoot,
        'app/src/main/java/com/fasttrade/app'
      );

      // Write native files
      fs.writeFileSync(path.join(javaDir, 'SmsModule.kt'), SMS_MODULE_KT);
      fs.writeFileSync(path.join(javaDir, 'SmsPackage.kt'), SMS_PACKAGE_KT);

      // Patch MainApplication.kt to register SmsPackage
      const mainAppPath = path.join(javaDir, 'MainApplication.kt');
      let src = fs.readFileSync(mainAppPath, 'utf8');

      if (!src.includes('SmsPackage()')) {
        src = src.replace(
          'PackageList(this).packages.apply {',
          'PackageList(this).packages.apply {\n              add(SmsPackage())'
        );
        fs.writeFileSync(mainAppPath, src);
      }

      return cfg;
    },
  ]);

  return config;
}

module.exports = withSmsPermission;
