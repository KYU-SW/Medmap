package kr.medmap.app;

import android.os.Bundle;

import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    @Override
    public void onCreate(Bundle savedInstanceState) {
        registerPlugin(WhisperPlugin.class);
        registerPlugin(DeviceSttPlugin.class);
        super.onCreate(savedInstanceState);
    }
}
