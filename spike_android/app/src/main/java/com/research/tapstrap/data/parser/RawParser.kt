package com.research.tapstrap.data.parser

import java.nio.ByteBuffer
import java.nio.ByteOrder

/**
 * Tap Strap 2 raw-mode packet parser.
 * Ported from Mac Python implementation at finger/tapstrap/collect_gestures.py:parse_raw
 *
 * Packet structure (little-endian):
 *   [4-byte timestamp] [N * 2-byte int16 values]
 *   If timestamp high bit set -> accl, N = 15 (5 fingers × XYZ)
 *   Otherwise -> imu, N = 6 (gyro XYZ + accel XYZ)
 *
 * Truncated packets (BLE MTU too small) keep N_actual < N_expected.
 */
object RawParser {

    private const val RAW_MSG_TYPE_BIT = 0x80000000L

    data class Message(
        val type: String,         // "accl" or "imu"
        val nExpected: Int,
        val nActual: Int,
        val timestamp: Long,
        val payload: IntArray,
    ) {
        override fun equals(other: Any?) = other is Message &&
            type == other.type && timestamp == other.timestamp && payload.contentEquals(other.payload)
        override fun hashCode(): Int {
            var r = type.hashCode(); r = 31 * r + timestamp.hashCode(); r = 31 * r + payload.contentHashCode(); return r
        }
    }

    fun parse(data: ByteArray): List<Message> {
        val result = mutableListOf<Message>()
        val buf = ByteBuffer.wrap(data).order(ByteOrder.LITTLE_ENDIAN)
        while (buf.remaining() >= 4) {
            val tsRaw = buf.int.toLong() and 0xFFFFFFFFL
            if (tsRaw == 0L) break
            val isAccl = (tsRaw and RAW_MSG_TYPE_BIT) != 0L
            val ts = if (isAccl) tsRaw and (RAW_MSG_TYPE_BIT - 1) else tsRaw
            val nExpected = if (isAccl) 15 else 6
            val payload = IntArray(nExpected) { 0 }
            var nActual = 0
            for (i in 0 until nExpected) {
                if (buf.remaining() >= 2) {
                    payload[i] = buf.short.toInt(); nActual++
                } else break
            }
            result.add(Message(if (isAccl) "accl" else "imu", nExpected, nActual, ts, payload))
        }
        return result
    }
}
