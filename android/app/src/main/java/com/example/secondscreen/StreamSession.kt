package com.example.secondscreen

import android.media.MediaCodec
import android.media.MediaFormat
import android.os.Build
import android.util.Log
import android.view.MotionEvent
import android.view.Surface
import java.io.DataInputStream
import java.io.IOException
import java.io.OutputStream
import java.net.ConnectException
import java.net.InetSocketAddress
import java.net.Socket
import java.net.SocketTimeoutException
import java.nio.ByteBuffer
import java.util.concurrent.LinkedBlockingQueue
import kotlin.concurrent.thread
import kotlin.math.min

/**
 * Connects to the PC server (through `adb reverse`, so it is just localhost),
 * announces the surface size, then decodes the incoming H.264 access units
 * straight onto [surface]. Touch events are sent back to the PC.
 *
 * Wire format: see server/second_screen_server.py
 *
 * Reconnect strategy: exponential backoff from [BACKOFF_INITIAL_MS] to [BACKOFF_MAX_MS],
 * resetting on a successful connection.
 */
class StreamSession(
    private val surface: Surface,
    private val surfaceWidth: Int,
    private val surfaceHeight: Int,
    private val onStatus: (String?) -> Unit,
) {
    companion object {
        private const val TAG = "UsbSecondScreen"
        private const val PORT = 7878
        private const val MAX_FRAME_BYTES = 16 * 1024 * 1024
        private const val MSG_HELLO = 0
        private const val MSG_TOUCH = 1

        // Reconnect backoff parameters
        private const val BACKOFF_INITIAL_MS = 1000L
        private const val BACKOFF_MAX_MS = 5000L
        private const val BACKOFF_MULTIPLIER = 1.5
    }

    @Volatile private var running = true
    @Volatile private var connected = false
    @Volatile private var socket: Socket? = null
    private val outgoing = LinkedBlockingQueue<ByteArray>()
    private var worker: Thread? = null

    fun start() {
        worker = thread(name = "ss-net") { connectLoop() }
    }

    fun stop() {
        running = false
        try { socket?.close() } catch (_: IOException) {}
        worker?.interrupt()
    }

    // --- touch -> PC -------------------------------------------------------------

    fun sendTouch(ev: MotionEvent, viewWidth: Int, viewHeight: Int) {
        if (!connected || viewWidth <= 0 || viewHeight <= 0) return
        when (ev.actionMasked) {
            MotionEvent.ACTION_DOWN, MotionEvent.ACTION_POINTER_DOWN ->
                queueTouch(ev, ev.actionIndex, 0, viewWidth, viewHeight)
            MotionEvent.ACTION_MOVE ->
                for (i in 0 until ev.pointerCount) queueTouch(ev, i, 1, viewWidth, viewHeight)
            MotionEvent.ACTION_UP, MotionEvent.ACTION_POINTER_UP ->
                queueTouch(ev, ev.actionIndex, 2, viewWidth, viewHeight)
            MotionEvent.ACTION_CANCEL ->
                for (i in 0 until ev.pointerCount) queueTouch(ev, i, 2, viewWidth, viewHeight)
        }
    }

    private fun queueTouch(ev: MotionEvent, index: Int, action: Int, vw: Int, vh: Int) {
        if (action == 1 && outgoing.size > 200) return  // drop stale moves if the link stalls
        val x = (ev.getX(index) / vw * 65535f).coerceIn(0f, 65535f).toInt()
        val y = (ev.getY(index) / vh * 65535f).coerceIn(0f, 65535f).toInt()
        val slot = ev.getPointerId(index) % 10
        outgoing.offer(message(MSG_TOUCH, action, slot, x, y))
    }

    private fun message(type: Int, action: Int, slot: Int, x: Int, y: Int): ByteArray =
        ByteBuffer.allocate(8)  // big-endian by default
            .put(type.toByte()).put(action.toByte()).put(slot.toByte()).put(0)
            .putShort(x.toShort()).putShort(y.toShort())
            .array()

    // --- connection ----------------------------------------------------------------

    private fun connectLoop() {
        var backoffMs = BACKOFF_INITIAL_MS
        var consecutiveFailures = 0

        while (running) {
            onStatus("Waiting for the PC…\n\nStart the server on your computer and keep USB debugging on.")
            try {
                streamOnce()
                // Successful connection — reset backoff
                backoffMs = BACKOFF_INITIAL_MS
                consecutiveFailures = 0
            } catch (e: ConnectException) {
                consecutiveFailures++
                Log.d(TAG, "connection refused (attempt $consecutiveFailures): ${e.message}")
                onStatus(
                    "Connection refused.\n\n" +
                    "Make sure the server is running and adb reverse is set up:\n" +
                    "  adb reverse tcp:7878 tcp:7878"
                )
            } catch (e: SocketTimeoutException) {
                consecutiveFailures++
                Log.d(TAG, "connection timed out (attempt $consecutiveFailures): ${e.message}")
                onStatus(
                    "Connection timed out.\n\n" +
                    "Check that USB debugging is enabled and the cable is connected."
                )
            } catch (e: IOException) {
                consecutiveFailures++
                Log.d(TAG, "connection ended (attempt $consecutiveFailures): ${e.message}")
                onStatus("Connection lost: ${e.message ?: "Unknown I/O error"}\n\nReconnecting…")
            } catch (e: InterruptedException) {
                return
            } catch (e: CodecException) {
                consecutiveFailures++
                Log.e(TAG, "codec error", e)
                onStatus("Video decoder error: ${e.message}\n\nTry restarting the app.")
            } catch (e: Exception) {
                consecutiveFailures++
                Log.e(TAG, "stream error", e)
                onStatus("Error: ${e.message}")
            }
            connected = false
            if (!running) return

            // Exponential backoff sleep
            Log.d(TAG, "reconnecting in ${backoffMs}ms (failure #$consecutiveFailures)")
            try {
                Thread.sleep(backoffMs)
            } catch (_: InterruptedException) {
                return
            }
            backoffMs = min((backoffMs * BACKOFF_MULTIPLIER).toLong(), BACKOFF_MAX_MS)
        }
    }

    private fun streamOnce() {
        val s = Socket()
        s.tcpNoDelay = true
        s.connect(InetSocketAddress("127.0.0.1", PORT), 2000)
        socket = s
        val input = DataInputStream(s.getInputStream().buffered(1 shl 16))
        val out = s.getOutputStream()

        out.write(message(MSG_HELLO, 0, 0, surfaceWidth, surfaceHeight))
        out.flush()
        var w = input.readUnsignedShort()
        var h = input.readUnsignedShort()
        if (w == 0 || h == 0) { w = surfaceWidth; h = surfaceHeight }  // server does not know the size

        outgoing.clear()
        val codec = createDecoder(w, h)
        val drainer = thread(name = "ss-drain") { drain(codec) }
        val writer = thread(name = "ss-write") { writeLoop(out) }
        connected = true
        onStatus(null)
        try {
            var buf = ByteArray(1 shl 18)
            while (running) {
                val len = input.readInt()
                if (len <= 0 || len > MAX_FRAME_BYTES) throw IOException("bad frame length $len")
                if (buf.size < len) buf = ByteArray(len)
                input.readFully(buf, 0, len)
                queueFrame(codec, buf, len)
            }
        } finally {
            connected = false
            try { s.close() } catch (_: IOException) {}
            writer.interrupt()
            drainer.join(500)
            try { codec.stop() } catch (_: Exception) {}
            codec.release()
        }
    }

    private fun writeLoop(out: OutputStream) {
        try {
            while (true) {
                out.write(outgoing.take())
                out.flush()
            }
        } catch (_: Exception) {
            // interrupted or socket closed
        }
    }

    // --- decoding ------------------------------------------------------------------

    /** Custom exception to distinguish codec errors in the connect loop. */
    private class CodecException(message: String, cause: Throwable? = null) : Exception(message, cause)

    private fun createDecoder(w: Int, h: Int): MediaCodec {
        val format = MediaFormat.createVideoFormat(MediaFormat.MIMETYPE_VIDEO_AVC, w, h)
        format.setInteger(MediaFormat.KEY_PRIORITY, 0)  // real-time
        format.setInteger(MediaFormat.KEY_OPERATING_RATE, Short.MAX_VALUE.toInt())
        if (Build.VERSION.SDK_INT >= 30) format.setInteger(MediaFormat.KEY_LOW_LATENCY, 1)
        format.setInteger("vendor.qti-ext-dec-low-latency.enable", 1)  // Qualcomm; ignored elsewhere

        val codec = try {
            MediaCodec.createDecoderByType(MediaFormat.MIMETYPE_VIDEO_AVC)
        } catch (e: Exception) {
            throw CodecException("Failed to create H.264 decoder — device may not support AVC decoding", e)
        }

        try {
            codec.configure(format, surface, null, 0)
        } catch (e: Exception) {
            codec.release()
            throw CodecException("Failed to configure decoder for ${w}x${h} — unsupported resolution?", e)
        }

        try {
            codec.start()
        } catch (e: Exception) {
            codec.release()
            throw CodecException("Failed to start decoder", e)
        }

        return codec
    }

    /** One access unit (SPS/PPS inline on keyframes) per input buffer. */
    private fun queueFrame(codec: MediaCodec, data: ByteArray, len: Int) {
        while (running && connected) {
            val index = try {
                codec.dequeueInputBuffer(50_000)
            } catch (e: IllegalStateException) {
                Log.e(TAG, "dequeueInputBuffer failed — codec in error state", e)
                throw CodecException("Decoder dequeueInputBuffer failed", e)
            }
            if (index < 0) continue
            val input = codec.getInputBuffer(index) ?: return
            input.clear()
            input.put(data, 0, len)
            try {
                codec.queueInputBuffer(index, 0, len, System.nanoTime() / 1000, 0)
            } catch (e: IllegalStateException) {
                Log.e(TAG, "queueInputBuffer failed", e)
                throw CodecException("Decoder queueInputBuffer failed", e)
            }
            return
        }
    }

    /** Show every decoded frame immediately; never wait for a presentation time. */
    private fun drain(codec: MediaCodec) {
        val info = MediaCodec.BufferInfo()
        while (connected) {
            try {
                val index = codec.dequeueOutputBuffer(info, 10_000)
                if (index >= 0) codec.releaseOutputBuffer(index, true)
            } catch (e: IllegalStateException) {
                Log.w(TAG, "drain: codec in error state, stopping drain", e)
                return
            }
        }
    }
}
