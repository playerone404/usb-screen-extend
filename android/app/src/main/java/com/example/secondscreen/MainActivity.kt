package com.example.secondscreen

import android.app.Activity
import android.os.Build
import android.os.Bundle
import android.view.SurfaceHolder
import android.view.View
import android.view.WindowInsets
import android.view.WindowManager
import com.example.secondscreen.databinding.ActivityMainBinding

/**
 * Full-screen SurfaceView that shows the H.264 stream coming from the PC.
 * All networking and decoding lives in [StreamSession].
 */
class MainActivity : Activity(), SurfaceHolder.Callback {

    private lateinit var binding: ActivityMainBinding
    private var session: StreamSession? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        if (Build.VERSION.SDK_INT >= 28) {
            window.attributes.layoutInDisplayCutoutMode =
                WindowManager.LayoutParams.LAYOUT_IN_DISPLAY_CUTOUT_MODE_SHORT_EDGES
        }

        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        binding.surfaceView.holder.addCallback(this)
        binding.surfaceView.setOnTouchListener { _, event ->
            session?.sendTouch(event, binding.surfaceView.width, binding.surfaceView.height)
            true
        }

        binding.statusView.text = getString(R.string.status_connecting)
    }

    override fun onWindowFocusChanged(hasFocus: Boolean) {
        super.onWindowFocusChanged(hasFocus)
        if (hasFocus) hideSystemUi()
    }

    @Suppress("DEPRECATION")
    private fun hideSystemUi() {
        if (Build.VERSION.SDK_INT >= 30) {
            window.setDecorFitsSystemWindows(false)
            window.insetsController?.let {
                it.hide(WindowInsets.Type.systemBars())
                it.systemBarsBehavior = android.view.WindowInsetsController.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
            }
        } else {
            window.decorView.systemUiVisibility = (View.SYSTEM_UI_FLAG_FULLSCREEN
                    or View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                    or View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
                    or View.SYSTEM_UI_FLAG_LAYOUT_STABLE
                    or View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
                    or View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION)
        }
    }

    private fun showStatus(text: String?) {
        runOnUiThread {
            binding.statusView.text = text ?: ""
            binding.statusView.visibility = if (text == null) View.GONE else View.VISIBLE
        }
    }

    // --- SurfaceHolder.Callback ------------------------------------------------

    override fun surfaceCreated(holder: SurfaceHolder) {}

    override fun surfaceChanged(holder: SurfaceHolder, format: Int, width: Int, height: Int) {
        if (session == null && width > 0 && height > 0) {
            session = StreamSession(holder.surface, width, height, ::showStatus).also { it.start() }
        }
    }

    override fun surfaceDestroyed(holder: SurfaceHolder) {
        session?.stop()
        session = null
    }
}
