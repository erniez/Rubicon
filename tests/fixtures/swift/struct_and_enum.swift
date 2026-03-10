struct Config {
    let database: DatabaseConnection
    var cache: CacheManager
    var retryCount: Int
}

enum AppState: Codable {
    case loading
    case loaded
}
