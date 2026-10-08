// swift-tools-version: 6.0
// Root manifest, so that an application can depend on this repository at a tag:
//   .package(url: "https://github.com/Nicolas78240/WODCraft", exact: "1.1.1")
// It builds the same sources as swift/WODCraftKit/Package.swift (where the tests run).
import PackageDescription

let package = Package(
    name: "WODCraftKit",
    platforms: [.iOS(.v16), .macOS(.v13), .watchOS(.v9)],
    products: [
        .library(name: "WODCraftKit", targets: ["WODCraftKit"]),
    ],
    targets: [
        .target(
            name: "WODCraftKit",
            path: "swift/WODCraftKit/Sources/WODCraftKit",
            resources: [
                .copy("Resources/catalog.json"),
                .copy("Resources/library.json"),
                .copy("Resources/workout.schema.json"),
            ]
        ),
    ],
    swiftLanguageModes: [.v6]
)
