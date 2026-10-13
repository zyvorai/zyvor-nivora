// SPDX-License-Identifier: BUSL-1.1
import Foundation
import NetworkExtension

// Entry point of the content-filter system extension: NetworkExtension instantiates the provider
// class named under NEProviderClasses in Info.plist (FilterDataProvider).
autoreleasepool {
    NEProvider.startSystemExtensionMode()
}
dispatchMain()
