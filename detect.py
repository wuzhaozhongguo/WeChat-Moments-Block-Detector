import os
import re
import subprocess
import time
import xml.etree.ElementTree as ET
from collections import Counter

# 定义要查找的节点标签和属性值
node_tag = "node"
uiautomator_file_name = "window_dump.xml"


def click_by_text(xml_path, text):
    # 解析XML文件te
    tree = ET.parse(xml_path)
    root = tree.getroot()

    # 遍历XML树，查找符合条件的节点
    for elem in root.iter(node_tag):
        if text == elem.attrib.get("text", ""):
            text_center = bounds_str_to_center(elem.attrib.get("bounds", ""))
            subprocess.run(
                f"adb shell input tap {text_center[0]} {text_center[1]}".split()
            )
            return True

    return False

def click_by_id(xml_path, resource_id):
    # 解析XML文件te
    tree = ET.parse(xml_path)
    root = tree.getroot()

    # 遍历XML树，查找符合条件的节点
    for elem in root.iter(node_tag):
        if resource_id == elem.attrib.get("resource-id", ""):
            text_center = bounds_str_to_center(elem.attrib.get("bounds", ""))
            subprocess.run(
                f"adb shell input tap {text_center[0]} {text_center[1]}".split()
            )
            return True

    return False


def click_back_button():
    click_by_id(uiautomator_file_name, "com.tencent.mm:id/actionbar_up_indicator_btn")


def find_node_bounds(xml_path):
    # 解析XML文件
    tree = ET.parse(xml_path)
    root = tree.getroot()

    # 查找第一个class属性为androidx.recyclerview.widget.RecyclerView的节点
    recycler_view = root.find(
        ".//*[@class='androidx.recyclerview.widget.RecyclerView']"
    )
    if recycler_view is None:
        return None

    # 查到「xxx个朋友」的元素的边界
    footer_bounds = []
    last_item = recycler_view.findall("*")[-1]
    last_item_inner_items = last_item.findall(node_tag)
    if (
        len(last_item_inner_items) == 1
        and len(last_item_inner_items[0].findall(node_tag)) == 0
    ):
        footer_bounds = last_item_inner_items[0].attrib.get("bounds")
        print(
            f"footer_bounds={footer_bounds}, footer={last_item_inner_items[0].attrib.get('text')}"
        )

    # 查到所有朋友元素的边界和昵称
    result = []
    # 遍历XML树
    iter = root.iter()
    friend_item_resource_id = ""
    for element in iter:
        # 根据「朋友元素的节点id」获取「朋友元素的边界位置」和「朋友昵称」
        if friend_item_resource_id:
            if element.attrib.get("resource-id") == friend_item_resource_id:
                # 获取bounds和text值
                bounds = element.attrib.get("bounds")
                text = element.attrib.get("text")
                # 将结果添加到列表
                result.append((bounds, text))
        # 找到目录节点A - #节点中的下下一个元素的resource-id作为朋友元素的id
        elif element.attrib.get("text") and re.match(
            r"^[A-Z#]$", element.attrib.get("text")
        ):
            # 获取下下一个节点的resource-id值
            next(iter)
            friend_item_element = next(iter)
            if friend_item_element is not None:
                # 获取「朋友元素的节点id」
                friend_item_resource_id = friend_item_element.attrib.get("resource-id")
                print("resource_id=" + friend_item_resource_id)
                # 获取bounds和text值
                bounds = friend_item_element.attrib.get("bounds")
                text = friend_item_element.attrib.get("text")
                # 将结果添加到列表
                result.append((bounds, text))
                continue

    # 如果没找到字母A-#之后的元素，那么寻找RecyclerView中resource-id出现最频繁的ID作name的ID
    if not friend_item_resource_id:
        friend_item_resource_id = Counter([item.attrib.get("resource-id") for item in root.iter() if item.attrib.get("resource-id")]).most_common(1)[0][0]
        print(f"如果没找到字母A-#之后的元素，智能查找到的元素ID为{friend_item_resource_id}")
        if friend_item_resource_id:
            for element in recycler_view.iter():
                if element.attrib.get("resource-id") == friend_item_resource_id:
                    # 获取bounds和text值
                    bounds = element.attrib.get("bounds")
                    text = element.attrib.get("text")
                    # 将结果添加到列表
                    result.append((bounds, text))

    # 返回结果列表
    return result, get_bounds(recycler_view.attrib.get("bounds")), footer_bounds


def bounds_str_to_center(bound):
    left, top, right, bottom = get_bounds(bound)
    center = [(left + right) // 2, (top + bottom) // 2]
    return center


def get_bounds(bound):
    [left_top, right_bottom] = bound.split("][")
    left_top = left_top[1:]
    [left, top] = [str(edge) for edge in left_top.split(",")]
    right_bottom = right_bottom[:-1]
    [right, bottom] = [str(edge) for edge in right_bottom.split(",")]
    return int(left), int(top), int(right), int(bottom)


def exit_with_postprocess():
    if os.path.exists(uiautomator_file_name):
        os.remove(uiautomator_file_name)
    exit(1)


def back_reenter(back_times, reenter_text):
    for i in range(back_times):
        subprocess.run("adb shell input keyevent 4".split())
        time.sleep(1)
    print("再次读取UI布局中…")
    result = subprocess.run(
        "adb shell uiautomator dump --compressed".split(), capture_output=True
    )
    if "ERROR" in str(result.stderr):
        print("错误：拿不到UI布局，退出")
        exit_with_postprocess()
    else:
        subprocess.run("adb pull /sdcard/window_dump.xml .".split())
        clicked = click_by_text(uiautomator_file_name, reenter_text)
        if clicked:
            print("等待0.5s")
            time.sleep(0.5)
            return True
        else:
            print(f"错误：个人页找不到“{reenter_text}”入口，退出")
            exit_with_postprocess()


def pull_window_dump():
    result = subprocess.run(
        "adb shell uiautomator dump --compressed".split(), capture_output=True
    )

    if "ERROR" in str(result.stderr):
        print("错误：尝试了停止动画和返回重试，还是获取不到UI布局，退出")
        exit_with_postprocess()

    subprocess.run("adb pull /sdcard/window_dump.xml .".split())
    return True

def is_moments_photo_not_empty(name):
    # 解析XML文件
    tree = ET.parse(uiautomator_file_name)
    root = tree.getroot()
    for element in root.iter():
        content_desc = element.get("content-desc", "")
        if content_desc:
            match = re.match(r"朋友圈个人相册,共(\d+)张", content_desc)
            if match:
                count = match.group(1)
                print(f'{name}的朋友圈有[{count}]张照片')
                return int(count) > 0


def check_if_moments_close(item_bounds, name):
    center = bounds_str_to_center(item_bounds)
    print(f'点击[{name}]:{item_bounds}')
    subprocess.run("adb shell input tap {} {}".format(center[0], center[1]).split())
    pull_window_dump()

    if is_moments_photo_not_empty(name):
        print(f"{name}的朋友圈当前[打开]")
        click_back_button()
        return False

    if click_by_text(uiautomator_file_name, "朋友圈") == True:
        pull_window_dump()
        close = check_if_moments_close_right_now()
        print(f"{name}的朋友圈当前[{'关闭' if close else '打开'}]")
        click_back_button()
        pull_window_dump()
        click_back_button()
        return close
    else:
        print("错误：尝试进入朋友圈失败")
        exit_with_postprocess()
        return False


def check_if_moments_close_right_now():
    tree = ET.parse(uiautomator_file_name)
    root = tree.getroot()
    list_view = root.find(".//*[@class='android.widget.ListView']")
    if list_view is None:
        print("错误：没找到朋友圈ListView")
        exit_with_postprocess()
        return False
    else:
        if len(list_view) < 2:
            print("错误：朋友圈ListView内只有" + str(len(list_view)) + "个元素")
            exit_with_postprocess()
            return False
        elif (
            len(list_view) == 2
        ):  # 朋友圈ListView里面只有2个元素，即[头像+昵称+签名]、[分割线]
            last_linear_layout = list(list_view.findall("*"))[::-1][0]
            # [分割线]中间如果没有文案（类似'朋友仅展示最近三天的朋友圈'），即朋友圈不可见
            return len(last_linear_layout.findall(node_tag)) == 0
        else:
            return False


if __name__ == "__main__":
    footer_bounds = []
    result = []

    while True:
        print("读取UI布局中…")
        
        success = pull_window_dump()
        if not success:
            break

        last_footer_bounds = footer_bounds
        friend_items, list_container_bounds, footer_bounds = find_node_bounds(
            uiautomator_file_name
        )

        print("当前页面显示的好友个数=" + str(len(friend_items)))

        if last_footer_bounds and footer_bounds == last_footer_bounds:
            if len(result) == 0:
                print("检测全部完成，所有好友都可以看到朋友圈")    
            else:
                print("检测全部完成，看不到朋友圈的好友有:")
                for i in result:
                    print(i)
            exit_with_postprocess()
            break

        for item in friend_items:
            item_bounds, name = item
            if name == '微信团队' or name == '文件传输助手':
                continue
            close = check_if_moments_close(item_bounds, name)
            if close == True:
                if name not in result:
                    result.append(name)        

        # print("通讯录列表容器边界: " + str(list_container_bounds))
        list_container_h_center = (
            list_container_bounds[0] + list_container_bounds[2]
        ) // 2
        list_container_top = list_container_bounds[1]
        list_container_bottom = list_container_bounds[3]

        print(f'截止当前，看不到朋友圈的好友有：{result}')

        print("划动翻页…")
        subprocess.run(
            "adb shell input swipe {0} {1} {2} {3} 550".format(
                list_container_h_center,
                list_container_bottom - list_container_h_center,
                list_container_h_center,
                list_container_top,
            ).split(" ")
        )
        # print("停止飞滚")
        # subprocess.run(
        #     "adb shell input tap {} {}".format(
        #         list_container_h_center, list_container_top + 100
        #     ).split()
        # )
        print(
            "================================================================================"
        )
