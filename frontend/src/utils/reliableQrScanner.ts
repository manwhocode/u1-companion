import QrScanner from 'qr-scanner'
import { createWorker } from 'qr-scanner/qr-scanner-worker.min.js'

// Use the same software decoder for photos and video. Avoid inconsistent
// experimental BarcodeDetector implementations on mobile browsers.
QrScanner.createQrEngine = async () => createWorker()
export default QrScanner
